# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""
from os import path

import yaml
from rest_framework import serializers


class ApigwPermissionGrantSerializer(serializers.Serializer):
    apps = serializers.ListField(child=serializers.CharField(help_text="app_code"))
    permissions = serializers.ListField(child=serializers.CharField(help_text="resource_id"))

    def validate_permissions(self, permissions: list):
        allow_permissions = []
        dir_path = path.dirname(path.dirname(path.abspath(__file__)))
        with open(
            path.join(dir_path, "management", "commands", "data", "api-resources.yml"), "r", encoding="utf-8"
        ) as f:
            resources = yaml.load(f, Loader=yaml.FullLoader)
            for resource in resources["paths"].values():
                allow_permissions.extend(
                    [
                        r["operationId"]
                        for r in resource.values()
                        if r["x-bk-apigateway-resource"]["allowApplyPermission"]
                    ]
                )
        not_allow_permissions = set(permissions) - set(allow_permissions)
        if not_allow_permissions:
            raise serializers.ValidationError(f"exist not allowed permissions: {not_allow_permissions}")
        return permissions
