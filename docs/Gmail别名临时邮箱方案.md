# Gmail 别名临时邮箱方案（点号 + +tag）

## 1. 背景与目标

你当前的临时邮箱服务是自建的 `@metoolbot.top` 收信系统，用于 AWS Builder ID 注册流程的验证码收取。

你希望尝试一种“看起来不同、但最终都进同一主 Gmail 收件箱”的注册邮箱生成方式，也就是：
- **点号别名**：Gmail 忽略本地名（`@gmail.com` 前）里的所有 `.`  
- **+tag 别名**：`+` 后的标签被忽略，邮件仍进入主邮箱

该方案的本质是：把“临时邮箱”实现为**你主 Gmail 的动态收件地址生成器**，而不是自建一个新的域名收件系统。

## 2. 规则验证（你给出的推导是对的）

### 2.1 点号规则

Gmail 会忽略本地名中的点号，因此类似：
- `royal.hotkiss99@gmail.com`
- `r.oy.al.h.o.t.ch.kis.s99@gmail.com`

最终都会投递到同一个主收件箱。可参考 Google 邮件别名/地址说明与相关说明：  
- [Gmail Help - Send emails from a different address or alias](https://support.google.com/mail/answer/22370)
- [Do Dots Matter in Gmail?](https://emailvariations.com/posts/gmail-dots-dont-matter)

### 2.2 +tag 规则

`name+tag@gmail.com` 会投递到 `name@gmail.com`。可参考：  
- [Gmail Help - Gmail Aliases](https://support.google.com/mail/answer/22370)
- [Do Dots Matter in Gmail?](https://emailvariations.com/posts/gmail-dots-dont-matter)

> 注意：不同网站对 `+` 的表单校验不一定一致，有些会拒绝或裁剪 `+`。因此需要做兜底策略（见第 6 节）。

## 3. 为什么自建服务能“读到验证码”

AWS Builder/注册只需要填写一个“可接收验证码的邮箱地址”。在 Gmail 的规则下：
- 你生成的每个“别名地址”本质上仍投递到**同一个主 Gmail 收件箱**
- 因此你只要能用 IMAP/或 Gmail API 读取主邮箱，就能从中筛选出验证码

自建服务要做的关键是：**能生成别名地址 + 能从主 Gmail 里筛出验证码邮件**。

## 4. 实现方案（建议架构）

### 4.1 组件拆分

建议按 Provider 模式做，类似你当前 `email_service.py` 的接口：
- `create_temp_email()`：生成别名邮箱并返回别名地址（以及用于筛选/验证的标识）
- `wait_for_verification_email()`：轮询主 Gmail，筛出与当前别名对应的验证码

新增 Provider 示例文件（建议）：
- `src/services/gmail_alias_service.py`

### 4.2 别名生成算法

你可以用两段拼接生成每次唯一的“看起来不同”的地址：

1) **点号变体**：在主用户名里随机插入 `.`  
2) **+tag 随机串**：在 `+` 后拼接 `8-16` 位随机串（字母/数字）

生成样式（示例）：
- 主账号：`royalhotkiss99@gmail.com`
- 动态别名：`r.oy.al.h.o.t.ch.kis.s99+q1oqzb4r@gmail.com`

### 4.3 收件箱如何实现（关键难点）

你需要从主 Gmail 读取邮件并过滤出与别名相关的验证码。常见做法是 IMAP：

- `imaplib.IMAP4_SSL("imap.gmail.com", 993)`
- 使用 **OAuth 或 App Passwords** 进行认证

Google 明确建议第三方客户端使用 OAuth；对于需要兼容的旧客户端，使用 2FA 后的 **App Password**。参考：
- [Sign in with app passwords - Gmail Help](https://support.google.com/mail/answer/185833)
- [Set up Gmail with a third-party email client](https://support.google.com/a/answer/9003945)

## 5. 部署与认证要点（必须先确认）

### 5.1 账号侧准备

要用 IMAP 读取 Gmail，通常需要：
- 主 Gmail 开启 2FA
- 生成 16 位 App Password（用于 IMAP 登录）

参考：
- [Sign in with app passwords - Gmail Help](https://support.google.com/mail/answer/185833)

### 5.2 IMAP 并发与速率限制

Gmail 对 IMAP 连接/带宽有严格限制，过多并发或下载会触发临时封禁或限速。参考：
- [Gmail bandwidth limits (Google Workspace Help)](https://knowledge.workspace.google.com/admin/gmail/gmail-bandwidth-limits)
- [Gmail bandwidth limits | Google Workspace Help](https://support.google.com/a/answer/1071518?hl=en)

因此在你的脚本中要做到：
- 全程尽量保持**单连接**
- 每次注册流程结束后释放 IMAP 连接（logout/close）
- 限制轮询频率（你现有的 `poll_interval` 体系可以复用）

## 6. 与 AWS / 风控相关的注意事项

### 6.1 AWS 对“已使用过的邮箱”不可逆占用

AWS 可能把你尝试过注册的邮箱当作“已用邮箱”，即使未完成注册也可能占用。
因此：每次都要生成**新的 +tag/点号变体**，不要复用同一个别名。参考 AWS 讨论：
- [Issue with AWS account creation | AWS re:Post](https://repost.aws/questions/QUWm-2OBgJS9aCvUDp8oxDww/issue-with-aws-account-creation)

### 6.2 某些网站可能拒绝包含 `+` 的邮箱

部分表单会校验 `+`，导致注册失败。建议准备兜底策略：
- 优先用 `base_user+random@g`
- 若页面校验拒绝：改为“纯点号变体”但仍保持唯一（不含 `+`）

参考（站点对 `+` 的接受性差异）：
- [Gmail Generator + Dot Trick Guide](https://www.scaledmail.com/blogs/gmail-generator-guide)

## 7. 与你当前项目的集成建议

你当前的流程：
- 浏览器自动到 AWS Builder
- 填写邮箱
- 等待验证码邮件（当前依赖你自建临时邮箱 API）

接入方式：
1) 增加 `GMAIL_ALIAS` Provider 分支
2) `create_temp_email()` 改为：
   - 生成别名地址（返回给前端/浏览器填写）
   - 记录“当前别名 tag”用于筛选验证码（例如按 `To`/`recipient`）
3) `wait_for_verification_email()` 改为：
   - 用 IMAP 轮询主邮箱
   - 从邮件里提取 6 位验证码（你现在的 `extract_verification_code()` 可复用）
4) 日志与结果记录：
   - 把别名地址、主邮箱、tag、时间戳写入 `accounts.jsonl` 便于回溯

## 8. 安全与合规提醒

- 这类用途请仅限你自己的账号/个人测试，避免用于垃圾注册、恶意用途。
- 不要把 `Gmail App Password` 提交到 git；使用环境变量或 `.env` 注入。
- 建议为注册流程使用单独的“注册 Gmail 池”，避免影响你的日常收件与信誉。

## 9. 建议的落地验证顺序（推荐）

1) 先验证生成的别名地址能正常投递到主 Gmail（手动发一封测试）
2) 再验证 IMAP 拉取与验证码提取逻辑正确
3) 最后把 Provider 接入自动注册流程，先跑到 `STOP_AFTER_CONTINUE=1`（你已有该开关）

