#!/bin/bash
set -e
export $(cat tests/interface.env | xargs)
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest tests/interface tests/plugins tests/project_settings tests/contrib
set +e

set -e
export $(cat tests/engine.env | xargs)
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest -x --cov-append tests/engine tests/decision_table
set +e