#!/usr/bin/env bash
# RoadLens 一键启动脚本
# 用法: ./start.sh
set -e

cd "$(dirname "$0")"

# 选择解释器：优先 python3，回退 python
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "未找到 python3 / python，请先安装 Python 3.9+" >&2
  exit 1
fi

# 优先使用虚拟环境（若存在）
if [ -d "venv" ]; then
  source venv/bin/activate
fi

echo "安装依赖（如缺失）..."
"$PY" -m pip install -q -r requirements.txt || true

echo "启动 RoadLens -> http://localhost:8124 ..."
"$PY" -m server.app "$@"
