#!/bin/bash

RELEASE_VERSION=$1

ver=$(awk '/^(app_version|appVersion):/ {gsub(/"/, "", $2); print $2}' app_desc.yaml)
echo "current version: ${ver}"

# version num replace
sed -i.bak -E "s/^(app_version|appVersion):.*/\1: \"${RELEASE_VERSION}\"/" app_desc.yaml
rm app_desc.yaml.bak

