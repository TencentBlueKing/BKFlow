#!/bin/bash
set -e
export $(cat tests/engine.env | xargs)
echo $BKFLOW_MODULE_TYPE
pytest -x --cov-append tests/engine tests/decision_table