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

from bkflow.space.credential.bkapp import BkAppCredential
from bkflow.space.exceptions import CredentialTypeNotSupport


class CredentialDispatcher:
    CREDENTIAL_MAP = {"BK_APP": BkAppCredential}

    def __init__(self, credential_type, data):
        credential_cls = self.CREDENTIAL_MAP.get(credential_type)
        if credential_cls is None:
            raise CredentialTypeNotSupport(_("type={}".format(type)))
        self.instance = credential_cls(data=data)

    def display_value(self):
        return self.instance.display_value()

    def value(self):
        return self.instance.value()

    def validate_data(self):
        return self.instance.validate_data()
