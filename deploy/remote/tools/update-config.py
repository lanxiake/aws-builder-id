#!/usr/bin/env python3
"""更新VPS上的配置：切换到英语区域。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

SCRIPT = """
import yaml
p = '/opt/aws-builder-id/config/config.yaml'
cfg = yaml.safe_load(open(p))
cfg['region']['current'] = 'usa'
yaml.dump(cfg, open(p, 'w'), allow_unicode=True, sort_keys=False)
c = yaml.safe_load(open(p))
print(f"region: {c['region']['current']}")
print(f"locale: {c['region']['profiles']['usa']['locale']}")
print("OK")
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
c.connect(HOST, username="root", pkey=key, timeout=30, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
with sftp.open("/tmp/_cfg_update.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, o, e = c.exec_command("source /opt/aws-builder-id/.venv/bin/activate; python3 /tmp/_cfg_update.py", timeout=15)
print(o.read().decode(errors="replace"))
c.close()
