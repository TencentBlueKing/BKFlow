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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers


class CreateCredentialSerializer(serializers.Serializer):
    name = serializers.CharField(help_text=_("凭证名称"), max_length=32, required=True)
    desc = serializers.CharField(help_text=_("凭证描述"), max_length=32, required=False)
    type = serializers.CharField(help_text=_("凭证类型"), max_length=32, required=True)
    content = serializers.JSONField(help_text=_("凭证内容"), required=True)
