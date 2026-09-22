#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/../bkflow/apigw/docs"
# Rebuild to avoid retaining removed resources in the published archive.
rm -f apigw-docs.zip
zip -r apigw-docs.zip zh en
