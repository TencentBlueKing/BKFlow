#!/bin/bash
set -e
export $(cat tests/interface.env | xargs)
echo "Running ${BKFLOW_MODULE_TYPE} unit tests..."
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table
