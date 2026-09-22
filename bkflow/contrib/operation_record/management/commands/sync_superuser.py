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
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    def add_arguments(self, parser):
        """支持显式授权用户，发布时仍兼容原有环境变量。"""
        parser.add_argument("--usernames", help="Comma-separated usernames; defaults to BKFLOW_INIT_SUPERUSERS")

    @transaction.atomic
    def handle(self, *args, **kwargs):
        User = apps.get_model("account", "User")
        usernames = kwargs.get("usernames") or os.getenv("BKFLOW_INIT_SUPERUSERS", "")
        usernames = list(dict.fromkeys(name.strip() for name in usernames.split(",") if name.strip()))
        if not usernames:
            return

        if settings.ENABLE_MULTI_TENANT_MODE:
            users = list(User.objects.select_for_update().filter(username__in=usernames))
            if len(users) != len(usernames) or any(user.tenant_id != "system" for user in users):
                raise CommandError("Multi-tenant superusers must be existing users of the system tenant; log in first")
            User.objects.filter(pk__in=[user.pk for user in users]).update(
                is_staff=True, is_active=True, is_superuser=True
            )
            return

        for username in usernames:
            User.objects.update_or_create(
                username=username, defaults={"is_staff": True, "is_active": True, "is_superuser": True}
            )
