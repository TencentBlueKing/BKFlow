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
from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

from bkflow.permission.models import Token


@periodic_task(run_every=crontab(minute="*/10"))
def delete_expired_token():
    # 假设token的过期时间为一小时，一天有2000个用户操作了100个流程，会生成大概200000个token
    # 此时的批量删除的数量级大概是可以接受的
    Token.objects.filter(expired_time__lt=timezone.now() - settings.TOKEN_RETENTION_TIME).delete()
