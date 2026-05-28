#!/usr/bin/env bash
# 兼容入口 → deploy/vps/bootstrap.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vps/bootstrap.sh" "$@"
