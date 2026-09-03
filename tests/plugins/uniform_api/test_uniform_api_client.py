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
from django.conf import settings

from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.pipeline_plugins.query.uniform_api.uniform_api import (
    UniformAPIMetaSerializer,
)
from bkflow.pipeline_plugins.query.uniform_api.utils import (
    UniformAPIClient,
    resolve_meta_url,
)
from bkflow.utils.api_client import HttpRequestResult


@pytest.fixture
def v4_meta():
    """提供包含完整轮询配置的 V4 元数据。"""
    return {
        "id": "open_plugin_001",
        "name": "JOB 执行作业",
        "plugin_source": "builtin",
        "plugin_code": "job_execute_task",
        "plugin_version": "1.2.0",
        "wrapper_version": "v4.0.0",
        "url": "https://bk-sops.example/open-plugin-runs",
        "methods": ["POST"],
        "inputs": [],
        "outputs": [],
        "polling": {
            "url": "https://bk-sops.example/open-plugin-runs/status",
            "task_tag_key": "open_plugin_run_id",
            "success_tag": {"key": "status", "value": "SUCCEEDED"},
            "fail_tag": {"key": "status", "value": "FAILED"},
            "running_tag": {"key": "status", "value": "RUNNING"},
        },
    }


class TestUniformAPIClient:
    def setup_method(self, method):
        self.client = UniformAPIClient()

    def test_method_not_allowed(self):
        with pytest.raises(APIRequestError):
            self.client.request(method="PUT", url="http://www.example.com", data={})

    def test_request_check_url_from_apigw(self, monkeypatch):
        monkeypatch.setattr(settings, "SKIP_APIGW_CHECK", False)
        # 跳过配置检查
        client = UniformAPIClient(from_apigw_check=False)
        response = client.request(method="GET", url="http://www.example.com", data={})
        assert isinstance(response, HttpRequestResult)

        # 配置检查且未配置正则
        with pytest.raises(APIRequestError):
            self.client.request(method="GET", url="http://www.example.com", data={})

        # 配置检查且配置正则
        monkeypatch.setattr(settings, "BK_APIGW_NETLOC_PATTERN", "^(.*?)www.example.com")
        response = self.client.request(method="GET", url="http://www.example.com", data={})
        assert isinstance(response, HttpRequestResult)

    def test_list_response_schema_validation(self):
        # 不符合格式的响应
        with pytest.raises(ValidationError):
            # 缺少 total 字段
            invalid_instance = {
                "apis": [
                    {
                        "id": "api1",
                        "name": "test",
                        "meta_url": "http://www.example.com",
                    }
                ]
            }
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

        # 符合格式的响应
        valid_instance = {
            "total": 1,
            "apis": [
                {
                    "id": "api1",
                    "name": "test",
                    "meta_url": "http://www.example.com",
                }
            ],
        }
        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

    def test_meta_response_schema_validation(self):
        # 不符合格式的响应
        with pytest.raises(ValidationError):
            # method 不符合枚举类型
            invalid_instance = {
                "id": "api1",
                "name": "test",
                "url": "http://www.example.com",
                "methods": ["GET", "POST", "PUT"],
                "inputs": [{"name": "test", "key": "test", "required": True, "type": "string"}],
            }
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

        # 符合格式的响应
        valid_instance = {
            "id": "api1",
            "name": "test",
            "url": "http://www.example.com",
            "methods": ["GET", "POST"],
            "inputs": [{"name": "test", "key": "test", "required": True, "type": "string"}],
        }
        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_meta_response_allows_legacy_extra_plugin_code(self):
        """旧协议允许附加字段；仅带 plugin_code 的 V3 响应不能被当成残缺 V4。"""
        valid_instance = {
            "id": "api1",
            "name": "test",
            "url": "http://www.example.com",
            "methods": ["GET", "POST"],
            "inputs": [{"name": "test", "key": "test", "required": True, "type": "string"}],
            "plugin_code": "legacy_job",
        }
        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_validate_v4_list_meta_contract(self):
        valid_instance = {
            "total": 1,
            "apis": [
                {
                    "id": "open_plugin_001",
                    "name": "JOB 执行作业",
                    "plugin_source": "builtin",
                    "plugin_code": "job_execute_task",
                    "wrapper_version": "v4.0.0",
                    "default_version": "1.2.0",
                    "latest_version": "1.3.0",
                    "versions": ["1.2.0", "1.3.0"],
                    "meta_url_template": "https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                }
            ],
        }

        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)

    def test_validate_v4_detail_meta_requires_polling_object_tags(self):
        invalid_instance = {
            "id": "open_plugin_001",
            "name": "JOB 执行作业",
            "plugin_source": "builtin",
            "plugin_code": "job_execute_task",
            "plugin_version": "1.2.0",
            "wrapper_version": "v4.0.0",
            "url": "https://bk-sops.example/open-plugin-runs",
            "methods": ["POST"],
            "inputs": [],
            "outputs": [],
            "polling": {
                "url": "https://bk-sops.example/open-plugin-runs/status",
                "task_tag_key": "open_plugin_run_id",
                "success_tag": "SUCCEEDED",
                "fail_tag": {"key": "status", "value": "FAILED", "msg_key": "data.error_message"},
                "running_tag": {"key": "status", "value": "RUNNING"},
            },
        }

        with pytest.raises(ValidationError):
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize("polling_fields", ({}, {"polling": {}}), ids=("omitted", "empty-object"))
    def test_validate_v4_detail_meta_without_polling(self, v4_meta, polling_fields):
        """V4 未传 polling 或传空对象都表示不轮询。"""
        v4_meta.pop("polling")
        v4_meta.update(polling_fields)

        self.client.validate_response_data(v4_meta, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize("missing_key", ("url", "task_tag_key", "success_tag", "fail_tag", "running_tag"))
    def test_validate_v4_detail_meta_rejects_incomplete_polling(self, v4_meta, missing_key):
        """V4 非空轮询配置仍须包含全部五个必填字段。"""
        v4_meta["polling"].pop(missing_key)

        with pytest.raises(ValidationError):
            self.client.validate_response_data(v4_meta, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize("tag_key", ("success_tag", "fail_tag", "running_tag"))
    @pytest.mark.parametrize("missing_key", ("key", "value"))
    def test_validate_v4_detail_meta_rejects_incomplete_polling_tags(self, v4_meta, tag_key, missing_key):
        """兼容空 polling 不得放宽非空配置内的状态标记校验。"""
        v4_meta["polling"][tag_key].pop(missing_key)

        with pytest.raises(ValidationError):
            self.client.validate_response_data(v4_meta, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize(
        "polling",
        (None, [], "", False, {"unknown": True}),
        ids=("null", "array", "string", "boolean", "unknown-field-only"),
    )
    def test_validate_v4_detail_meta_rejects_invalid_polling(self, v4_meta, polling):
        """仅兼容空对象，不将其他假值或仅含未知字段的对象视为不轮询。"""
        v4_meta["polling"] = polling

        with pytest.raises(ValidationError):
            self.client.validate_response_data(v4_meta, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize("wrapper_version", (None, "v2.0.0", "v3.0.0"))
    @pytest.mark.parametrize("polling_fields", ({}, {"polling": {}}), ids=("omitted", "empty-object"))
    def test_validate_legacy_detail_meta_without_polling(self, wrapper_version, polling_fields):
        """旧协议省略 polling 或传空对象的兼容行为保持不变。"""
        meta = {
            "id": "api1",
            "name": "test",
            "url": "https://bk-sops.example/run/",
            "methods": ["POST"],
            "inputs": [],
            **polling_fields,
        }
        if wrapper_version is not None:
            meta["wrapper_version"] = wrapper_version

        self.client.validate_response_data(meta, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_validate_v4_detail_meta_requires_complete_contract(self):
        invalid_instance = {
            "id": "open_plugin_001",
            "name": "JOB 执行作业",
            "plugin_source": "builtin",
            "plugin_code": "job_execute_task",
            "plugin_version": "1.2.0",
            "wrapper_version": "v4.0.0",
            "url": "https://bk-sops.example/open-plugin-runs",
            "methods": ["POST"],
            "inputs": [],
        }

        with pytest.raises(ValidationError):
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_validate_complete_v4_detail_meta_contract(self):
        valid_instance = {
            "id": "open_plugin_001",
            "name": "JOB 执行作业",
            "plugin_source": "builtin",
            "plugin_code": "job_execute_task",
            "plugin_version": "legacy",
            "wrapper_version": "v4.0.0",
            "url": "https://bk-sops.example/open-plugin-runs",
            "methods": ["POST"],
            "inputs": [],
            "form_schema": {
                "type": "object",
                "required": ["biz_id"],
                "properties": {
                    "biz_id": {
                        "type": "number",
                        "title": "业务 ID",
                        "ui:component": {"name": "bk-input", "props": {"type": "number"}},
                    }
                },
            },
            "outputs": [{"name": "作业实例 ID", "key": "job_instance_id"}],
            "polling": {
                "url": "https://bk-sops.example/open-plugin-runs/status",
                "task_tag_key": "open_plugin_run_id",
                "success_tag": {"key": "status", "value": "SUCCEEDED", "data_key": "data.outputs"},
                "fail_tag": {"key": "status", "value": "FAILED", "msg_key": "data.error_message"},
                "running_tag": {"key": "status", "value": "RUNNING"},
            },
        }

        self.client.validate_response_data(valid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    @pytest.mark.parametrize(
        "invalid_fields",
        (
            {"forms": {"input": None}},
            {"form_context": []},
        ),
        ids=("forms-missing-output", "form-context-not-object"),
    )
    def test_validate_v4_native_form_fields(self, invalid_fields):
        """V4 原生表单字段必须符合 input/output 与 context 对象契约。"""
        invalid_instance = {
            "id": "open_plugin_001",
            "name": "JOB 执行作业",
            "plugin_source": "builtin",
            "plugin_code": "job_execute_task",
            "plugin_version": "1.2.0",
            "wrapper_version": "v4.0.0",
            "url": "https://bk-sops.example/open-plugin-runs",
            "methods": ["POST"],
            "inputs": [],
            "outputs": [],
            **invalid_fields,
        }

        with pytest.raises(ValidationError):
            self.client.validate_response_data(invalid_instance, self.client.UNIFORM_API_META_RESPONSE_DATA_SCHEMA)

    def test_resolve_meta_url_returns_plain_meta_url_first(self):
        assert (
            resolve_meta_url(
                meta_url="https://bk-sops.example/open-plugins/open_plugin_001",
                meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                version="1.2.0",
            )
            == "https://bk-sops.example/open-plugins/open_plugin_001"
        )

    def test_resolve_meta_url_formats_template_with_version(self):
        assert (
            resolve_meta_url(
                meta_url="",
                meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                version="1.2.0",
            )
            == "https://bk-sops.example/open-plugins/open_plugin_001?version=1.2.0"
        )

    def test_resolve_meta_url_requires_version_for_template(self):
        with pytest.raises(ValidationError):
            resolve_meta_url(
                meta_url="",
                meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                version="",
            )

    def test_meta_serializer_accepts_versioned_meta_url_template(self):
        serializer = UniformAPIMetaSerializer(
            data={
                "template_id": 1,
                "meta_url_template": "https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
                "version": "1.2.0",
                "source_key": "sops",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["meta_url_template"].endswith("{version}")
        assert serializer.validated_data["version"] == "1.2.0"

    def test_meta_serializer_requires_meta_url_or_template(self):
        serializer = UniformAPIMetaSerializer(
            data={
                "template_id": 1,
            }
        )

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors
