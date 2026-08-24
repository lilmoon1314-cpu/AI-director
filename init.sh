#!/usr/bin/env bash
# 兼容入口：环境预检查后等价于 make setup（命令契约见 INIT.md / Makefile）
set -euo pipefail

cd "$(dirname "$0")"

command -v uv >/dev/null 2>&1 || { echo "错误: 缺少 uv，安装见 https://docs.astral.sh/uv/"; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "错误: 缺少 pnpm，请执行: npm i -g pnpm"; exit 1; }

exec make setup
