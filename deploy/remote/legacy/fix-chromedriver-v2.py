#!/usr/bin/env python3
"""修复 ChromeDriver：正确从 zip 中提取 ELF 二进制。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

SCRIPT = r"""
import subprocess, re, urllib.request, zipfile, io, os, shutil

chrome_out = subprocess.check_output(["google-chrome", "--version"]).decode().strip()
ver = re.search(r"(\d+)\.\d+\.\d+\.\d+", chrome_out)
full = ver.group(0)
major = int(ver.group(1))
print(f"Chrome: {full}")

url = f"https://storage.googleapis.com/chrome-for-testing-public/{full}/linux64/chromedriver-linux64.zip"
print(f"Download: {url}")
data = urllib.request.urlopen(url, timeout=120).read()

with zipfile.ZipFile(io.BytesIO(data)) as z:
    print("Zip contents:", z.namelist())
    for name in z.namelist():
        basename = os.path.basename(name)
        if basename == "chromedriver":
            content = z.read(name)
            if content[:4] == b'\x7fELF':
                dest = "/usr/local/bin/chromedriver"
                with open(dest, "wb") as f:
                    f.write(content)
                os.chmod(dest, 0o755)
                print(f"Installed ELF binary: {dest} ({len(content)} bytes)")
                break
    else:
        print("ERROR: No ELF chromedriver found in zip")
        raise SystemExit(1)

out = subprocess.check_output(["/usr/local/bin/chromedriver", "--version"]).decode().strip()
print(f"ChromeDriver: {out}")

uc_cache = os.path.expanduser("~/.local/share/undetected_chromedriver")
if os.path.isdir(uc_cache):
    shutil.rmtree(uc_cache)
    print(f"Cleared UC cache")
"""


def main():
    """上传并执行修复脚本。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    with sftp.open("/tmp/_fix_cd2.py", "w") as f:
        f.write(SCRIPT)
    sftp.close()

    _, stdout, stderr = c.exec_command(
        "source /opt/aws-builder-id/.venv/bin/activate && python /tmp/_fix_cd2.py",
        timeout=120,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-2000:])
    print("exit:", stdout.channel.recv_exit_status())
    c.close()


if __name__ == "__main__":
    main()
