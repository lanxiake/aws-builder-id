#!/usr/bin/env bash
# show-dkim.sh: 展示 dkim1 公钥并生成对应的 DNS TXT 记录
set -euo pipefail

cd /mnt/d/yangd/dkim-keys

echo '===== 公钥 PEM (dkim1.public.pem) ====='
cat dkim1.public.pem
echo

PUB=$(grep -v '^-----' dkim1.public.pem | tr -d '\n')

echo '===== Base64 公钥（去掉 PEM 头/尾，单行） ====='
echo "$PUB"
echo

echo '===== DKIM TXT 记录值（单行，直接粘贴到大多数 DNS 控制台） ====='
echo "v=DKIM1; k=rsa; p=$PUB"
echo

echo '===== DKIM TXT 记录（BIND 风格，按 255 字符拆分） ====='
FULL="v=DKIM1; k=rsa; p=$PUB"
printf '%s' "$FULL" | fold -w 255 | awk '{printf "\"%s\" ", $0} END {print ""}'

echo
echo '===== 主机/名称 ====='
echo 'dkim1._domainkey   (完整域名: dkim1._domainkey.<你的域名>)'
