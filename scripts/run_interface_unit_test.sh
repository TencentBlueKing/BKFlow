#!/bin/bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "${ROOT_DIR}/.venv/bin/activate" ]; then
  source "${ROOT_DIR}/.venv/bin/activate"
fi
export $(cat tests/interface.env | xargs)
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=${PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION:-python}
echo $BKFLOW_MODULE_TYPE
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table
