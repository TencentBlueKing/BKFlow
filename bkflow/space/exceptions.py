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
from django.utils.translation import gettext_lazy as _

from bkflow.exceptions import BKFLOWException


class SpaceConfigDefaultValueNotExists(BKFLOWException):
    CODE = None
    MESSAGE = _("该空间配置项没有配置默认值")
    STATUS_CODE = 404


class CredentialOperateNotSupport(BKFLOWException):
    CODE = None
    MESSAGE = _("不支持该凭证操作")


class CredentialNotExists(BKFLOWException):
    CODE = None
    MESSAGE = _("凭证不存在")


class CredentialTypeNotSupport(BKFLOWException):
    CODE = None
    MESSAGE = _("不支持的凭证类型")


class SpaceNotExists(BKFLOWException):
    CODE = None
    MESSAGE = _("空间不存在")
