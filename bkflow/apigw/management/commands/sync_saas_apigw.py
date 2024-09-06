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

import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        definition_file_path = os.path.join(__file__.rsplit("/", 1)[0], "data/api-definition.yml")
        resources_file_path = os.path.join(__file__.rsplit("/", 1)[0], "data/api-resources.yml")

        print("[bkflow_engine_service]call sync_apigw_config with definition: %s" % definition_file_path)
        call_command("sync_apigw_config", file=definition_file_path)

        print("[bkflow_engine_service]call sync_apigw_stage with definition: %s" % definition_file_path)
        call_command("sync_apigw_stage", file=definition_file_path)

        print("[bkflow_engine_service]call sync_apigw_resources with resources: %s" % resources_file_path)
        call_command("sync_apigw_resources", file=resources_file_path)

        print("[bkflow_engine_service]call sync_resource_docs_by_archive with definition: %s" % definition_file_path)
        call_command("sync_resource_docs_by_archive", file=definition_file_path)

        print("[bkflow_engine_service]call create_version_and_release_apigw with definition: %s" % definition_file_path)
        call_command(
            "create_version_and_release_apigw",
            "--generate-sdks",
            file=definition_file_path,
            stage=settings.BKAPP_APIGW_SYNC_STAGE,
        )

        print("[bkflow_engine_service] call grant_apigw_permissions with definition: %s" % definition_file_path)
        call_command("grant_apigw_permissions", file=definition_file_path)

        print("[bkflow_engine_service]call fetch_apigw_public_key")
        call_command("fetch_apigw_public_key")
