#!/usr/bin/env python3
"""步骤1：用密码登录服务器，配置 SSH 公钥免密登录。"""
import os
import sys
import paramiko

HOST = "192.119.110.157"
USER = "root"
PUBKEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDH73bOZ7OWvjyrb356hsMu15GqBpPOv"
    "eMfUDYRmKsqmE+f9Jd6wie5uO3G4GoC2SEneQMyJ8O9LbNHEtCPv5wweo7Z00VYamTlj"
    "TvCayoRJ0/owS0Ksogq/JKtyTj0oG0sd8DIN+YWi+ZsW58uPjrhRIq0Yku55NEbLUJnl"
    "FthFf5LXYfJD4geMbdUw9ldKsZmNeorYDVg0i6ak0jZ2zEtr2JTbrfhngct5VefBltLnB"
    "AEH2OGQlXes52X4kjUWZTJV5bN90TbxaDZgwdawONeEo7M6sto3gLR3n+YtCUURHZNLl"
    "TO4m+t7ld6mkuSPCopPu79Kjfszqx4CV8PcRtf toolan-deploy"
)


def ssh_exec(client, cmd, timeout=60):
    """执行远程命令并打印输出。"""
    print(f"  >>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"  {out}")
    if err:
        print(f"  [stderr] {err}")
    return code, out


def main():
    """连接服务器并配置SSH密钥。"""
    password = os.environ.get("DEPLOY_PASS", "")
    if not password:
        print("请设置环境变量 DEPLOY_PASS")
        sys.exit(1)

    print(f"[1] 用密码连接 {USER}@{HOST} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30,
                   allow_agent=False, look_for_keys=False)
    print("  连接成功!")

    print("[2] 写入公钥到 authorized_keys ...")
    ssh_exec(client, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")
    # 检查是否已存在
    code, out = ssh_exec(client, f'grep -c "toolan-deploy" /root/.ssh/authorized_keys 2>/dev/null || echo 0')
    if out.strip() == "0":
        ssh_exec(client, f'echo "{PUBKEY}" >> /root/.ssh/authorized_keys')
        print("  公钥已添加")
    else:
        print("  公钥已存在，跳过")
    ssh_exec(client, "chmod 600 /root/.ssh/authorized_keys")

    print("[3] 确保 sshd 允许公钥认证 ...")
    ssh_exec(client, "sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config")
    ssh_exec(client, "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config")
    ssh_exec(client, "systemctl restart sshd")

    print("[4] 解除 fail2ban 封禁 ...")
    ssh_exec(client, "fail2ban-client unban --all 2>/dev/null || echo 'no fail2ban'")

    print("[5] 验证服务器基本信息 ...")
    ssh_exec(client, "uname -a")
    ssh_exec(client, "cat /etc/os-release | head -3")
    ssh_exec(client, "python3 --version")
    ssh_exec(client, "free -h | head -2")
    ssh_exec(client, "df -h / | tail -1")

    client.close()
    print("\n[完成] SSH 密钥配置完毕，现在可以用密钥登录了。")


if __name__ == "__main__":
    main()
