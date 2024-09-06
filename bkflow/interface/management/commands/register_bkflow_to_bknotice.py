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


from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from bkflow.interface.models import EnvironmentVariables


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if getattr(settings, "DISABLE_REGISTER_BKFLOW_TO_BKNOTICE", False):
            print("[register_bkflow_to_bknotice] disable register_bkflow_to_bknotice")
            return
        try:
            print("[register_bkflow_to_bknotice] call register_application...")
            call_command("register_application", raise_error=True)
            EnvironmentVariables.objects.update_or_create(defaults={"value": 1}, key="ENABLE_NOTICE_CENTER")
        except Exception as e:
            print(f"[register_bkflow_to_bknotice] err: {e}")
            EnvironmentVariables.objects.update_or_create(defaults={"value": 0}, key="ENABLE_NOTICE_CENTER")
