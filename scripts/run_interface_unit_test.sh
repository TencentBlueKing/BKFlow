#!/bin/bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "${ROOT_DIR}/.venv/bin/activate" ]; then
  source "${ROOT_DIR}/.venv/bin/activate"
fi
export $(cat tests/interface.env | xargs)
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}
echo $BKFLOW_MODULE_TYPE
# 独立进程验证真实并发，避免旧 Python 插件测试对进程内存限制的修改影响线程启动。
pytest tests/interface/permission/test_mysql_lifecycle.py tests/interface/permission/test_unified_migrations.py
pytest --cov-append --ignore=tests/interface/permission/test_mysql_lifecycle.py \
  --ignore=tests/interface/permission/test_unified_migrations.py \
  tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table tests/label
