#!/bin/bash

RELEASE_VERSION=$1
C_OS="$(uname)"
MAC_OS="Darwin"

ver=$(grep 'app_version:' app_desc_ce.yaml | cut -c 14-)
echo "current version: ${ver}"

# version num replace
if [ "$C_OS" == "$MAC_OS" ];then
    echo "app_version: \"${ver}\""
    sed -i.bak "s/app_version: ${ver}/app_version: \"${RELEASE_VERSION}\"/" app_desc_ce.yaml
    sed -i.bak "s/app_version: ${ver}/app_version: \"${RELEASE_VERSION}\"/" app_desc_sg.yaml
    rm app_desc_ce.yaml.bak app_desc_sg.yaml.bak
else
    sed -i "s/app_version: ${ver}/app_version: \"${RELEASE_VERSION}\"/" app_desc_ce.yaml
    sed -i "s/app_version: ${ver}/app_version: \"${RELEASE_VERSION}\"/" app_desc_sg.yaml
fi

