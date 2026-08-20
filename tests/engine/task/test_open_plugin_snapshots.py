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

import pytest

from bkflow.exceptions import ValidationError
from bkflow.task.open_plugin_snapshots import prepare_engine_task_extra_info
from bkflow.utils.pipeline import build_default_pipeline_tree


def build_v4_pipeline_tree():
    tree = build_default_pipeline_tree()
    activity = next(iter(tree["activities"].values()))
    activity["type"] = "ServiceActivity"
    activity["component"] = {
        "code": "uniform_api",
        "version": "v4.0.0",
        "api_meta": {"source_key": "sops"},
        "data": {
            "uniform_api_plugin_id": {"value": "open_plugin_001"},
            "uniform_api_plugin_version": {"value": "1.2.0"},
        },
    }
    return tree


def test_prepare_engine_task_extra_info_skips_plain_pipeline(mocker):
    """普通任务不请求 Interface 快照接口。"""
    mock_client = mocker.patch("bkflow.task.open_plugin_snapshots.InterfaceModuleClient")
    extra = {"notify_config": {"notify_type": {"fail": []}}}

    result = prepare_engine_task_extra_info(
        space_id=1,
        pipeline_tree=build_default_pipeline_tree(),
        extra_info=extra,
    )

    assert result == extra
    mock_client.assert_not_called()


def test_prepare_engine_task_extra_info_merges_v4_snapshots(mocker):
    """V4 任务创建前合并引用快照和 schema 快照。"""
    mock_client = mocker.patch("bkflow.task.open_plugin_snapshots.InterfaceModuleClient")
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": True,
        "data": {
            "reference_snapshot": [{"node_id": "node1", "plugin_id": "open_plugin_001"}],
            "schema_snapshot": {"node1": {"inputs": [], "plugin_id": "open_plugin_001"}},
        },
    }
    extra = {
        "notify_config": {"notify_type": {"fail": []}},
        "custom_context": {"credentials": {"gw": {"bk_app_secret": "SECRET_TOKEN"}}},
    }

    result = prepare_engine_task_extra_info(
        space_id=1,
        pipeline_tree=build_v4_pipeline_tree(),
        extra_info=extra,
        username="alice",
        scope_type="biz",
        scope_id="2",
    )

    assert result["notify_config"] == extra["notify_config"]
    assert result["custom_context"]["credentials"]["gw"]["bk_app_secret"] == "SECRET_TOKEN"
    assert result["plugin_reference_snapshot"][0]["plugin_id"] == "open_plugin_001"
    assert result["plugin_schema_snapshot"]["node1"]["plugin_id"] == "open_plugin_001"
    mock_client.return_value.build_open_plugin_snapshots.assert_called_once()
    payload = mock_client.return_value.build_open_plugin_snapshots.call_args[0][0]
    assert payload["mode"] == "prepare"
    assert payload["space_id"] == 1
    assert "extra_info" not in payload
    assert "SECRET_TOKEN" not in json.dumps(payload)
    assert "bk_app_secret" not in json.dumps(payload)


def test_prepare_engine_task_extra_info_raises_when_interface_fails(mocker):
    """Interface 快照接口失败时，不得继续创建任务。"""
    mock_client = mocker.patch("bkflow.task.open_plugin_snapshots.InterfaceModuleClient")
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": False,
        "message": "开放插件 [open_plugin_001] 在当前空间未开放",
    }

    with pytest.raises(ValidationError, match="在当前空间未开放"):
        prepare_engine_task_extra_info(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info={})
