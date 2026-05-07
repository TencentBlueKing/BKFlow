#!/bin/bash
set -e
export $(cat tests/interface.env | xargs)
pytest tests/interface tests/plugins tests/project_settings tests/contrib tests/decision_table tests/label
