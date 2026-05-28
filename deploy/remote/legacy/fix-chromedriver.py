#!/usr/bin/env python3
"""修复 ChromeDriver 版本不匹配问题。"""
import os
import paramiko

HOST = "192.119.110.157"
KEY_PATH = os.path.expanduser("~/.ssh/toolan_deploy.pem")

SCRIPT = r"""
import subprocess, re, urllib.request, zipfile, io, os, shutil, stat

chrome_out = subprocess.check_output(["google-chrome", "--version"]).decode().strip()
ver = re.search(r"(\d+)\.\d+\.\d+\.\d+", chrome_out)
if not ver:
    raise RuntimeError(f"Cannot parse Chrome version: {chrome_out}")
major = int(ver.group(1))
full = ver.group(0)
print(f"Chrome: {full}  major={major}")

# CfT endpoint
url = f"https://storage.googleapis.com/chrome-for-testing-public/{full}/linux64/chromedriver-linux64.zip"
print(f"Downloading: {url}")
try:
    data = urllib.request.urlopen(url, timeout=60).read()
except Exception as e:
    # fallback: latest for major
    print(f"Direct download failed ({e}), trying known-good-versions...")
    ep = f"https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    import json
    info = json.loads(urllib.request.urlopen(ep, timeout=30).read())
    candidates = [v for v in info["versions"] if v["version"].startswith(f"{major}.")]
    candidates = [v for v in candidates if "chromedriver" in v.get("downloads", {})]
    if not candidates:
        raise RuntimeError(f"No chromedriver for Chrome {major}")
    best = candidates[-1]
    dl = [d for d in best["downloads"]["chromedriver"] if d["platform"] == "linux64"][0]
    url = dl["url"]
    print(f"Fallback URL: {url}")
    data = urllib.request.urlopen(url, timeout=60).read()

with zipfile.ZipFile(io.BytesIO(data)) as z:
    for name in z.namelist():
        if name.endswith("chromedriver") and not name.endswith("/"):
            dest = "/usr/local/bin/chromedriver"
            with z.open(name) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            os.chmod(dest, 0o755)
            print(f"Installed: {dest}")
            break

out = subprocess.check_output(["/usr/local/bin/chromedriver", "--version"]).decode().strip()
print(f"ChromeDriver: {out}")

# Also clear UC cache
uc_cache = os.path.expanduser("~/.local/share/undetected_chromedriver")
if os.path.isdir(uc_cache):
    shutil.rmtree(uc_cache)
    print(f"Cleared UC cache: {uc_cache}")
"""

def main():
    """上传并执行修复脚本。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    c.connect(HOST, username="root", pkey=key, timeout=30,
              allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    with sftp.open("/tmp/_fix_cd.py", "w") as f:
        f.write(SCRIPT)
    sftp.close()

    _, stdout, stderr = c.exec_command(
        "source /opt/aws-builder-id/.venv/bin/activate && python /tmp/_fix_cd.py",
        timeout=120,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    print("exit:", stdout.channel.recv_exit_status())
    c.close()


if __name__ == "__main__":
    main()
