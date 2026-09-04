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
from bkflow.plugin.services.uniform_api_meta import (
    UniformAPIMetaError,
    extract_uniform_api_meta_data,
)
from bkflow.utils.api_client import HttpRequestResult


def _meta_data(**overrides):
    data = {
        "id": "sops_execute",
        "name": "标准运维执行",
        "url": "https://bk-sops.example/run/",
        "methods": ["POST"],
        "inputs": [{"key": "biz_id", "name": "业务ID", "type": "int", "required": True}],
        "desc": "执行标准运维流程",
    }
    data.update(overrides)
    return data


def _result(data=None, result=True, response_result=True, message=""):
    return HttpRequestResult(
        result=result,
        message=message,
        json_resp={
            "result": response_result,
            "message": message,
            "data": data if data is not None else _meta_data(),
        },
    )


def test_extract_uniform_api_meta_data_returns_valid_v2_payload():
    """合法 V2 meta 应原样返回 data。"""
    data = extract_uniform_api_meta_data(_result(), requested_version=None, catalog_wrapper_version="v2.0.0")

    assert data["id"] == "sops_execute"
    assert data["inputs"][0]["key"] == "biz_id"


@pytest.mark.parametrize("polling_fields", ({}, {"polling": {}}), ids=("omitted", "empty-object"))
def test_extract_uniform_api_meta_data_returns_v4_without_polling(polling_fields):
    """无轮询的 V4 插件详情应通过校验并原样返回。"""
    meta = _meta_data(
        wrapper_version="v4.0.0",
        plugin_source="builtin",
        plugin_code="job",
        plugin_version="1.2.0",
        outputs=[],
        **polling_fields,
    )

    data = extract_uniform_api_meta_data(
        _result(data=meta), requested_version="1.2.0", catalog_wrapper_version="v4.0.0"
    )

    assert data == meta


def test_extract_uniform_api_meta_data_rejects_http_failure():
    """传输层失败不得当作成功 meta。"""
    with pytest.raises(UniformAPIMetaError, match="network failed"):
        extract_uniform_api_meta_data(_result(result=False, message="network failed", data=None))


def test_extract_uniform_api_meta_data_rejects_business_failure():
    """provider 业务 result=false 不得当作成功 meta。"""
    with pytest.raises(UniformAPIMetaError, match="provider rejected"):
        extract_uniform_api_meta_data(_result(response_result=False, message="provider rejected", data=None))


def test_extract_uniform_api_meta_data_rejects_missing_data():
    """响应缺少 data 对象时必须失败。"""
    with pytest.raises(UniformAPIMetaError, match="data"):
        extract_uniform_api_meta_data(_result(data=[]))


def test_extract_uniform_api_meta_data_requires_v4_plugin_version():
    """V4 响应必须带可核对的 plugin_version。"""
    with pytest.raises(UniformAPIMetaError, match="plugin_version"):
        extract_uniform_api_meta_data(
            _result(),
            requested_version="1.2.0",
            catalog_wrapper_version="v4.0.0",
        )


def test_extract_uniform_api_meta_data_rejects_version_mismatch():
    """返回版本必须等于请求的精确版本。"""
    data = _meta_data(
        plugin_version="9.9.9",
        wrapper_version="v4.0.0",
        plugin_source="builtin",
        plugin_code="job",
        outputs=[],
    )
    with pytest.raises(UniformAPIMetaError, match="1.2.0.*9.9.9"):
        extract_uniform_api_meta_data(
            _result(data=data),
            requested_version="1.2.0",
            catalog_wrapper_version="v4.0.0",
        )


def test_extract_uniform_api_meta_data_rejects_invalid_schema():
    """缺少 url/methods 等必填字段时必须失败。"""
    with pytest.raises((UniformAPIMetaError, ValidationError)):
        extract_uniform_api_meta_data(_result(data={"id": "sops_execute", "name": "x", "inputs": []}))
