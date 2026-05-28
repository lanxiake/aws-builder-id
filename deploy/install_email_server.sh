#!/usr/bin/env bash
# 兼容入口 → deploy/vps/install-email-server.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vps/install-email-server.sh" "$@"
