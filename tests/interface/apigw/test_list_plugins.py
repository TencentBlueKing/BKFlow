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
from bkflow.apigw.serializers.plugin import (
    GetPluginSchemaSerializer,
    ListPluginsSerializer,
)


class TestListPluginsSerializer:
    def test_default_values(self):
        ser = ListPluginsSerializer(data={})
        assert ser.is_valid()
        assert ser.validated_data["without_detail"] is True
        assert ser.validated_data["limit"] == 100
        assert ser.validated_data["offset"] == 0

    def test_keyword_filter(self):
        ser = ListPluginsSerializer(data={"keyword": "脚本"})
        assert ser.is_valid()
        assert ser.validated_data["keyword"] == "脚本"

    def test_invalid_plugin_type(self):
        ser = ListPluginsSerializer(data={"plugin_type": "invalid"})
        assert not ser.is_valid()


class TestGetPluginSchemaSerializer:
    def test_code_required(self):
        ser = GetPluginSchemaSerializer(data={})
        assert not ser.is_valid()
        assert "code" in ser.errors

    def test_valid(self):
        ser = GetPluginSchemaSerializer(data={"code": "test_code"})
        assert ser.is_valid()
