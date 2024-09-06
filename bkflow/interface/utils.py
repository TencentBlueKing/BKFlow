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

from apigw_manager.apigw.authentication import UserModelBackend
from blueapps.account import get_user_model


class APIGWUserModelBackend(UserModelBackend):
    def __init__(self):
        self.user_model = get_user_model()

    def make_user(self, username: str):
        user, _ = self.user_model.objects.get_or_create(username=username)
        return user

    def authenticate(self, request, api_name, bk_username, verified, **credentials):
        if not verified:
            return self.make_anonymous_user(bk_username=bk_username)
        return self.make_user(bk_username)
