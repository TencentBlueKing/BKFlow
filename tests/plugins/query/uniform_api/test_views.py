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
import pytest

from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.query.uniform_api.uniform_api import (
    UniformAPIBaseSerializer,
    UniformAPICategorySerializer,
    UniformAPIListSerializer,
    UniformAPIMetaSerializer,
)


class TestUniformAPISerializers:
    """测试序列化器"""

    def test_base_serializer_requires_template_or_task_id(self):
        """测试基础序列化器需要 template_id 或 task_id"""
        serializer = UniformAPIBaseSerializer(data={})
        # 序列化器的 validate 方法会抛出 ValidationError
        with pytest.raises(ValidationError) as exc_info:
            serializer.is_valid(raise_exception=True)
        assert "template_id" in str(exc_info.value) or "task_id" in str(exc_info.value)

    def test_base_serializer_with_template_id(self):
        """测试基础序列化器使用 template_id"""
        serializer = UniformAPIBaseSerializer(data={"template_id": 1})
        assert serializer.is_valid() is True

    def test_base_serializer_with_task_id(self):
        """测试基础序列化器使用 task_id"""
        serializer = UniformAPIBaseSerializer(data={"task_id": "123"})
        assert serializer.is_valid() is True

    def test_base_serializer_with_both(self):
        """测试基础序列化器同时使用 template_id 和 task_id"""
        serializer = UniformAPIBaseSerializer(data={"template_id": 1, "task_id": "123"})
        assert serializer.is_valid() is True

    def test_category_serializer_valid(self):
        """测试分类序列化器有效数据"""
        serializer = UniformAPICategorySerializer(
            data={
                "template_id": 1,
                "scope_type": "project",
                "scope_value": "p1",
                "key": "test",
                "api_name": "default",
            }
        )
        assert serializer.is_valid() is True

    def test_category_serializer_minimal(self):
        """测试分类序列化器最小有效数据"""
        serializer = UniformAPICategorySerializer(data={"template_id": 1})
        assert serializer.is_valid() is True

    def test_category_serializer_all_optional(self):
        """测试分类序列化器所有可选字段"""
        serializer = UniformAPICategorySerializer(
            data={
                "task_id": "123",
                "scope_type": "business",
                "scope_value": "b1",
                "key": "search_key",
                "api_name": "custom_api",
            }
        )
        assert serializer.is_valid() is True
        assert serializer.validated_data["scope_type"] == "business"
        assert serializer.validated_data["api_name"] == "custom_api"

    def test_list_serializer_valid(self):
        """测试列表序列化器有效数据"""
        serializer = UniformAPIListSerializer(
            data={
                "template_id": 1,
                "limit": 10,
                "offset": 0,
                "scope_type": "project",
                "scope_value": "p1",
                "category": "cat1",
                "key": "test",
            }
        )
        assert serializer.is_valid() is True

    def test_list_serializer_defaults(self):
        """测试列表序列化器默认值"""
        serializer = UniformAPIListSerializer(data={"template_id": 1})
        assert serializer.is_valid() is True
        assert serializer.validated_data["limit"] == 50
        assert serializer.validated_data["offset"] == 0

    def test_list_serializer_custom_pagination(self):
        """测试列表序列化器自定义分页"""
        serializer = UniformAPIListSerializer(data={"template_id": 1, "limit": 100, "offset": 50})
        assert serializer.is_valid() is True
        assert serializer.validated_data["limit"] == 100
        assert serializer.validated_data["offset"] == 50

    def test_list_serializer_with_api_name(self):
        """测试列表序列化器带api_name"""
        serializer = UniformAPIListSerializer(data={"template_id": 1, "api_name": "custom_api"})
        assert serializer.is_valid() is True
        assert serializer.validated_data["api_name"] == "custom_api"

    def test_list_serializer_with_category(self):
        """测试列表序列化器带category"""
        serializer = UniformAPIListSerializer(data={"template_id": 1, "category": "system"})
        assert serializer.is_valid() is True
        assert serializer.validated_data["category"] == "system"

    def test_meta_serializer_requires_meta_url(self):
        """测试元数据序列化器需要 meta_url"""
        serializer = UniformAPIMetaSerializer(data={"template_id": 1})
        assert serializer.is_valid() is False
        assert "meta_url" in serializer.errors

    def test_meta_serializer_valid(self):
        """测试元数据序列化器有效数据"""
        serializer = UniformAPIMetaSerializer(data={"template_id": 1, "meta_url": "http://example.com/api/meta"})
        assert serializer.is_valid() is True

    def test_meta_serializer_with_scope(self):
        """测试元数据序列化器带scope"""
        serializer = UniformAPIMetaSerializer(
            data={
                "template_id": 1,
                "meta_url": "http://example.com/api/meta",
                "scope_type": "project",
                "scope_value": "p1",
            }
        )
        assert serializer.is_valid() is True
        assert serializer.validated_data["scope_type"] == "project"
        assert serializer.validated_data["scope_value"] == "p1"

    def test_meta_serializer_with_task_id(self):
        """测试元数据序列化器使用task_id"""
        serializer = UniformAPIMetaSerializer(data={"task_id": "123", "meta_url": "http://example.com/api/meta"})
        assert serializer.is_valid() is True
        assert serializer.validated_data["task_id"] == "123"

    def test_list_serializer_with_key(self):
        """测试列表序列化器带搜索key"""
        serializer = UniformAPIListSerializer(data={"template_id": 1, "key": "search_keyword"})
        assert serializer.is_valid() is True
        assert serializer.validated_data["key"] == "search_keyword"
