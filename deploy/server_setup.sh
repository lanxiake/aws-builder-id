#!/usr/bin/env bash
# 兼容入口 → deploy/vps/server-setup.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vps/server-setup.sh" "$@"
