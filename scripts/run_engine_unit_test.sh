#!/bin/bash
set -e
export $(cat tests/engine.env | xargs)
echo $BKFLOW_MODULE_TYPE
pytest -x tests/engine