#!/usr/bin/env bash
# 兼容入口 → deploy/vps/console-install.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vps/console-install.sh" "$@"
