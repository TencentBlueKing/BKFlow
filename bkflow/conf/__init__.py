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
from django.conf import settings as django_settings

from bkflow.conf import default_settings


class BKFLOWSettings:
    def __getattr__(self, key):
        if hasattr(django_settings, key):
            return getattr(django_settings, key)

        if hasattr(default_settings, key):
            return getattr(default_settings, key)

        raise AttributeError("Settings object has no attribute %s" % key)


settings = BKFLOWSettings()
