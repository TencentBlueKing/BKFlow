#!/bin/bash
source /root/.envs/bkflow/bin/activate

set -e
export $(cat tests/interface.env | xargs)
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table tests/label
set +e

set -e
export $(cat tests/engine.env | xargs)
echo "开始运行${BKFLOW_MODULE_TYPE}测试"
pytest --cov-append tests/engine tests/plugin_service
set +e