#!/usr/bin/env python3
"""在 VPS 配置美区静态代理、测试连通性并启动注册。"""
import os
import sys
import time
import urllib.parse
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")
REMOTE_DIR = "/opt/aws-builder-id"

# 格式 host:port:user:pass
PROXY_HOST = "70.39.242.6"
PROXY_PORT = "443"
PROXY_USER = "WMauHktAwcKX"
PROXY_PASS = os.environ.get("PROXY_PASS", "XXXXXXX")

PROXY_URL = (
    f"http://{urllib.parse.quote(PROXY_USER, safe='')}:"
    f"{urllib.parse.quote(PROXY_PASS, safe='')}@{PROXY_HOST}:{PROXY_PORT}"
)


def get_client():
    """SSH 连接。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)
    return c


def run(cmd, timeout=120):
    """执行远程命令。"""
    c = get_client()
    _, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    err = stderr.read().decode(errors="replace").strip()
    c.close()
    return code, out, err


def apply_config():
    """写入代理配置（不打印密码）。"""
    script = f'''
import yaml
p = "{REMOTE_DIR}/config/config.yaml"
cfg = yaml.safe_load(open(p))
cfg["email"]["worker_url"] = "http://127.0.0.1:18787"
cfg["region"]["current"] = "usa"
cfg["region"]["use_proxy"] = True
cfg["region"]["proxy_mode"] = "static"
cfg["region"]["proxy_url"] = {PROXY_URL!r}
cfg["browser"]["headless"] = True
yaml.dump(cfg, open(p, "w"), allow_unicode=True, sort_keys=False)
print("config ok")
print("region:", cfg["region"]["current"])
print("use_proxy:", cfg["region"]["use_proxy"])
print("proxy host:", {PROXY_HOST!r})
'''
    c = get_client()
    sftp = c.open_sftp()
    with sftp.open("/tmp/_proxy_cfg.py", "w") as f:
        f.write(script)
    sftp.close()
    _, stdout, stderr = c.exec_command(
        f"source {REMOTE_DIR}/.venv/bin/activate && python3 /tmp/_proxy_cfg.py",
        timeout=30,
    )
    out = stdout.read().decode(errors="replace")
    c.close()
    print(out)
    return "config ok" in out


def test_proxy():
    """测试代理出口 IP。"""
    test_script = f'''
import requests
proxy = {PROXY_URL!r}
proxies = {{"http": proxy, "https": proxy}}
try:
    r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=25)
    print("httpbin:", r.status_code, r.text.strip())
except Exception as e:
    print("httpbin FAIL:", e)
try:
    r2 = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=25)
    print("ipify:", r2.status_code, r2.text.strip())
except Exception as e:
    print("ipify FAIL:", e)
'''
    c = get_client()
    sftp = c.open_sftp()
    with sftp.open("/tmp/_proxy_test.py", "w") as f:
        f.write(test_script)
    sftp.close()
    _, stdout, _ = c.exec_command(
        f"source {REMOTE_DIR}/.venv/bin/activate && python3 /tmp/_proxy_test.py",
        timeout=60,
    )
    out = stdout.read().decode(errors="replace")
    c.close()
    print(out)
    return "200" in out and ("origin" in out.lower() or "ip" in out.lower())


def start_register_poll():
    """启动注册并轮询日志。"""
    run(
        f"cd {REMOTE_DIR} && source .venv/bin/activate && "
        "rm -f /tmp/register_run.log && "
        "nohup python src/runners/main.py > /tmp/register_run.log 2>&1 & "
        "echo $! > /tmp/register_run.pid && cat /tmp/register_run.pid"
    )
    print("\n注册已启动，跟踪日志...\n")
    last_size = 0
    for i in range(150):
        time.sleep(8)
        code, block, _ = run(
            "wc -c < /tmp/register_run.log 2>/dev/null; echo '---'; "
            "tail -20 /tmp/register_run.log 2>/dev/null; echo '---'; "
            "kill -0 $(cat /tmp/register_run.pid 2>/dev/null) 2>/dev/null && echo ALIVE || echo DEAD"
        )
        parts = block.split("---")
        try:
            size = int(parts[0].strip().split()[0])
        except (ValueError, IndexError):
            size = 0
        tail = parts[1] if len(parts) > 1 else ""
        status = parts[2] if len(parts) > 2 else ""
        if size != last_size:
            last_size = size
            print(f"[{(i+1)*8}s]")
            for line in tail.strip().split("\n")[-10:]:
                if line.strip():
                    print(f"  {line}")
        if "DEAD" in status:
            code, full, _ = run("tail -80 /tmp/register_run.log")
            print("\n=== 完整日志尾部 ===\n" + full)
            if "获取到验证码" in full:
                return 0
            if "error processing your request" in full.lower():
                return 1
            return 0
    return 2


def main():
    """主流程。"""
    print("=" * 55)
    print("配置美区代理")
    print(f"  {PROXY_HOST}:{PROXY_PORT} (用户 {PROXY_USER})")
    print("=" * 55)

    if not apply_config():
        print("配置写入失败")
        sys.exit(1)

    print("\n测试代理连通性...")
    if not test_proxy():
        print("代理测试失败，请检查密码是否为真实值（非 XXXXXXX 占位符）")
        sys.exit(1)

    print("\n启动注册（走代理）...")
    rc = start_register_poll()
    sys.exit(rc)


if __name__ == "__main__":
    main()
