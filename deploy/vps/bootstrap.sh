#!/usr/bin/env bash
# 在 VPS 控制台 (VNC) 一键执行：修复 SSH + 安装注册工具 + 自建邮箱 mx1.metoolbot.top
# 用法: curl -fsSL https://raw.githubusercontent.com/7836246/aws-builder-id/main/deploy/bootstrap_vps.sh | bash
# 或: bash deploy/vps/bootstrap.sh
set -euo pipefail

APP_DIR="/opt/aws-builder-id"
PUBKEY='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDH73bOZ7OWvjyrb356hsMu15GqBpPOveMfUDYRmKsqmE+f9Jd6wie5uO3G4GoC2SEneQMyJ8O9LbNHEtCPv5wweo7Z00VYamTljTvCayoRJ0/owS0Ksogq/JKtyTj0oG0sd8DIN+YWi+ZsW58uPjrhRIq0Yku55NEbLUJnlFthFf5LXYfJD4geMbdUw9ldKsZmNeorYDVg0i6ak0jZ2zEtr2JTbrfhngct5VefBltLnBAEH2OGQlXes52X4kjUWZTJV5bN90TbxaDZgwdawONeEo7M6sto3gLR3n+YtCUURHZNLlTO4m+t7ld6mkuSPCopPu79Kjfszqx4CV8PcRtf'

echo "==> 配置 root SSH 公钥..."
mkdir -p /root/.ssh && chmod 700 /root/.ssh
grep -qF "${PUBKEY}" /root/.ssh/authorized_keys 2>/dev/null || echo "${PUBKEY}" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
fail2ban-client unban --all 2>/dev/null || true

if [[ ! -d "${APP_DIR}/.git" ]]; then
  apt-get update -qq
  apt-get install -y -qq git
  git clone https://github.com/7836246/aws-builder-id.git "${APP_DIR}"
fi

export APP_DIR
bash "${APP_DIR}/deploy/vps/server-setup.sh"
bash "${APP_DIR}/deploy/services/vps-email/install.sh"

echo "==> 写入邮箱配置 mx1.metoolbot.top ..."
python3 <<'PY'
from pathlib import Path
import yaml
p = Path("/opt/aws-builder-id/config/config.yaml")
cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
cfg.setdefault("email", {})
cfg["email"]["worker_url"] = "https://mx1.metoolbot.top"
cfg["email"]["domain"] = "metoolbot.top"
p.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("config.yaml 已更新")
PY

echo ""
echo "请在 DNSPod 添加记录后测试:"
echo "  A    mx1  ->  $(curl -4 -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo "  MX   @    ->  mx1.metoolbot.top  优先级 10"
echo "  curl -s https://mx1.metoolbot.top/api/health"
