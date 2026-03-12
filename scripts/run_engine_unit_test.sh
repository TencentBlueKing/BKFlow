#!/bin/bash
set -e
export $(cat tests/engine.env | xargs)
echo "Running ${BKFLOW_MODULE_TYPE} unit tests..."
pytest --cov-append tests/engine tests/plugin_service