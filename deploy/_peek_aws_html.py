#!/usr/bin/env python3
import paramiko

PROXY = "http://WMauHktAwcKX:YiLkHvDOJs@70.39.242.6:443"
SCRIPT = f'''
import requests
p = {{"http": "{PROXY}", "https": "{PROXY}"}}
r = requests.get("https://builder.aws.com/start", proxies=p, timeout=45,
    headers={{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}})
print(r.text[:2000])
'''

key = paramiko.RSAKey.from_private_key_file(r"C:\Users\Administrator\.ssh\toolan_deploy.pem")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.119.110.157", username="root", pkey=key, timeout=30, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()
with sftp.open("/tmp/_peek.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/_peek.py", timeout=60)
print(o.read().decode(errors="replace"))
c.close()
