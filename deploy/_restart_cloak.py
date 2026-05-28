#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.119.110.157", username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY), timeout=30)
script = r"""
cd /opt/aws-builder-id
source .venv/bin/activate
pip install -q 'cloakbrowser[geoip]'
pkill -f run_cloak_register 2>/dev/null || true
sleep 1
nohup python scripts/run_cloak_register.py > /tmp/register_cloak.log 2>&1 &
sleep 45
tail -60 /tmp/register_cloak.log
"""
_, o, _ = c.exec_command(script, get_pty=True, timeout=300)
o.channel.recv_exit_status()
print(o.read().decode(errors="replace"))
c.close()
