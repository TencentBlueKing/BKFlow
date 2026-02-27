#!/bin/bash
set -e
export $(cat tests/interface.env | xargs)
echo $BKFLOW_MODULE_TYPE
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table tests/label
