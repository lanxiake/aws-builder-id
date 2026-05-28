#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/toolan_deploy.pem")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.119.110.157", username="root", pkey=paramiko.RSAKey.from_private_key_file(KEY), timeout=30)
_, o, _ = c.exec_command(
    "wc -c /tmp/register_cloak.log 2>/dev/null; echo '===='; "
    "tail -100 /tmp/register_cloak.log 2>/dev/null; echo '===='; "
    "pgrep -af 'cloak_register|run_cloak' || echo no_proc",
    get_pty=True,
    timeout=60,
)
o.channel.recv_exit_status()
print(o.read().decode(errors="replace"))
c.close()
