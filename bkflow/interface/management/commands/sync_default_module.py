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

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand

from bkflow.admin.models import IsolationLevel, ModuleType


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        print("sync default module info...")
        ModuleInfo = apps.get_model("bkflow_admin", "ModuleInfo")
        token = os.getenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", "")
        default_engine_entry = settings.BKAPP_DEFAULT_ENGINE_MODULE_ENTRY
        if token and default_engine_entry:
            module_info, create = ModuleInfo.objects.get_or_create(
                space_id=0,
                defaults={
                    "code": "default",
                    "url": default_engine_entry,
                    "token": token,
                    "type": ModuleType.TASK.value,
                    "isolation_level": IsolationLevel.ALL_RESOURCE.value,
                },
            )
            print(f"module info obj id: {module_info.id}, is_create: {create}")
