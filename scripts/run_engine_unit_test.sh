#!/bin/bash
set -e
export $(cat tests/engine.env | xargs)
echo $BKFLOW_MODULE_TYPE
pytest --cov-append tests/engine tests/plugin_service