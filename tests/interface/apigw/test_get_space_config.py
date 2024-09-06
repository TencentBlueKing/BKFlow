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
import json

from django.test import TestCase, override_settings

from bkflow.space.models import Space, SpaceConfig


class TestGetSpaceConfig(TestCase):
    url = "/apigw/get_space_configs/"

    @override_settings(
        BK_APIGW_REQUIRE_EXEMPT=True, MIDDLEWARE=("tests.interface.apigw.middlewares.OverrideMiddleware",)
    )
    def test_get_space_config(self):
        space = Space.objects.create(app_code="test", platform_url="http://test.com", name="space")

        url = "/apigw/space/{}/get_space_configs/".format(space.id)
        SpaceConfig.objects.create(space_id=space.id, name="token_expiration", text_value="1h")

        resp = self.client.get(path=url, data=None)

        resp_data = json.loads(resp.content)

        self.assertEqual(resp.status_code, 200)
        data = {"config": [{"key": "token_expiration", "value": "1h"}], "space_id": space.id}
        self.assertEqual(resp_data["data"], data)
