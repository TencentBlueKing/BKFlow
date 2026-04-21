#!/bin/bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "${ROOT_DIR}/.venv/bin/activate" ]; then
  source "${ROOT_DIR}/.venv/bin/activate"
elif [ -f /root/.envs/bkflow/bin/activate ]; then
  source /root/.envs/bkflow/bin/activate
fi

export $(cat tests/interface.env | xargs)
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table
set +e

set -e
export $(cat tests/engine.env | xargs)
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest --cov-append tests/engine tests/plugin_service
set +e
