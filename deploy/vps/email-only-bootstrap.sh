#!/usr/bin/env bash
# VNC 一键：仅部署邮箱（修复 SSH + 安装 mx1 邮箱服务）
set -euo pipefail
PUBKEY='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDH73bOZ7OWvjyrb356hsMu15GqBpPOveMfUDYRmKsqmE+f9Jd6wie5uO3G4GoC2SEneQMyJ8O9LbNHEtCPv5wweo7Z00VYamTljTvCayoRJ0/owS0Ksogq/JKtyTj0oG0sd8DIN+YWi+ZsW58uPjrhRIq0Yku55NEbLUJnlFthFf5LXYfJD4geMbdUw9ldKsZmNeorYDVg0i6ak0jZ2zEtr2JTbrfhngct5VefBltLnBAEH2OGQlXes52X4kjUWZTJV5bN90TbxaDZgwdawONeEo7M6sto3gLR3n+YtCUURHZNLlTO4m+t7ld6mkuSPCopPu79Kjfszqx4CV8PcRtf'

mkdir -p /root/.ssh && chmod 700 /root/.ssh
grep -qF "$PUBKEY" /root/.ssh/authorized_keys 2>/dev/null || echo "$PUBKEY" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
fail2ban-client unban --all 2>/dev/null || true

DEPLOY_DIR="/root/email-deploy"
mkdir -p "$DEPLOY_DIR"

if [[ -d /opt/aws-builder-id/deploy/services/vps-email ]]; then
  cp -f /opt/aws-builder-id/deploy/vps/install-email-server.sh "$DEPLOY_DIR/install_email_server.sh"
  mkdir -p "$DEPLOY_DIR/vps_email"
  cp -f /opt/aws-builder-id/deploy/services/vps-email/* "$DEPLOY_DIR/vps_email/"
elif [[ -d /opt/aws-builder-id/deploy/vps_email ]]; then
  cp -f /opt/aws-builder-id/deploy/install_email_server.sh "$DEPLOY_DIR/" 2>/dev/null || \
    cp -f /opt/aws-builder-id/deploy/vps/install-email-server.sh "$DEPLOY_DIR/install_email_server.sh"
  cp -rf /opt/aws-builder-id/deploy/vps_email "$DEPLOY_DIR/"
elif [[ -f "$DEPLOY_DIR/install_email_server.sh" ]]; then
  :
else
  apt-get update -qq && apt-get install -y -qq git
  git clone --depth 1 https://github.com/7836246/aws-builder-id.git /opt/aws-builder-id || true
  if [[ -d /opt/aws-builder-id/deploy/services/vps-email ]]; then
    cp -f /opt/aws-builder-id/deploy/vps/install-email-server.sh "$DEPLOY_DIR/install_email_server.sh"
    mkdir -p "$DEPLOY_DIR/vps_email"
    cp -f /opt/aws-builder-id/deploy/services/vps-email/* "$DEPLOY_DIR/vps_email/"
  elif [[ -d /opt/aws-builder-id/deploy/vps_email ]]; then
    cp -f /opt/aws-builder-id/deploy/install_email_server.sh "$DEPLOY_DIR/" 2>/dev/null || true
    cp -rf /opt/aws-builder-id/deploy/vps_email "$DEPLOY_DIR/"
  else
    echo "请上传 email-deploy.tar.gz 到 /root/ 后解压到 $DEPLOY_DIR"
    exit 1
  fi
fi

bash "$DEPLOY_DIR/install_email_server.sh"
