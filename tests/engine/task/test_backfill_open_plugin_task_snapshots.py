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

import io
import json

import pytest
from django.core.management import CommandError, call_command

from bkflow.task.models import TaskInstance
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


def snapshot_payload():
    return {
        "plugin_reference_snapshot": [{"node_id": "node1", "plugin_id": "open_plugin_001", "plugin_version": "1.2.0"}],
        "plugin_schema_snapshot": {
            "node1": {
                "schema_protocol_version": "open_plugin_snapshot.v1",
                "plugin_id": "open_plugin_001",
                "inputs": [],
            }
        },
    }


@pytest.mark.django_db
def test_engine_command_updates_task_extra_info(mocker):
    """Engine 环境能发现任务回填命令，并真正更新 TaskInstance.extra_info。"""
    task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info={})
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )
    extra = snapshot_payload()
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": True,
        "data": {
            "changed": True,
            "reference_snapshot": extra["plugin_reference_snapshot"],
            "schema_snapshot": extra["plugin_schema_snapshot"],
        },
    }

    stdout = io.StringIO()
    call_command("backfill_open_plugin_task_snapshots", stdout=stdout)

    task.refresh_from_db()
    assert task.extra_info["plugin_schema_snapshot"]["node1"]["plugin_id"] == "open_plugin_001"
    assert "updated_tasks=1" in stdout.getvalue()


@pytest.mark.django_db
def test_engine_command_dry_run_does_not_write(mocker):
    """dry-run 不写数据库。"""
    task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info={})
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": True,
        "data": {
            "changed": True,
            "reference_snapshot": snapshot_payload()["plugin_reference_snapshot"],
            "schema_snapshot": snapshot_payload()["plugin_schema_snapshot"],
        },
    }

    call_command("backfill_open_plugin_task_snapshots", "--dry-run")

    task.refresh_from_db()
    assert not task.extra_info.get("plugin_schema_snapshot")


@pytest.mark.django_db
def test_engine_command_skips_existing_snapshots(mocker):
    """已有非空快照不被覆盖；连续运行第二次更新数为 0。"""
    extra = snapshot_payload()
    TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info=extra)
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )

    stdout = io.StringIO()
    call_command("backfill_open_plugin_task_snapshots", stdout=stdout)

    mock_client.assert_not_called()
    assert "updated_tasks=0" in stdout.getvalue()


@pytest.mark.django_db
def test_engine_command_fails_when_interface_call_errors(mocker):
    """Interface 调用失败时命令明确失败，而不是报告 updated_tasks=0。"""
    TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info={})
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )
    mock_client.return_value.build_open_plugin_snapshots.side_effect = RuntimeError("interface down")

    with pytest.raises(CommandError, match="interface down"):
        call_command("backfill_open_plugin_task_snapshots")


@pytest.mark.django_db
def test_engine_command_keeps_task_when_exact_version_missing(mocker):
    """历史精确版本不存在时，任务保持不变并进入失败报告。"""
    task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info={})
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": False,
        "message": "开放插件 [open_plugin_001] 版本 [1.2.0] 当前不可用",
    }

    with pytest.raises(CommandError, match="failed_tasks=1"):
        call_command("backfill_open_plugin_task_snapshots")

    task.refresh_from_db()
    assert not task.extra_info.get("plugin_schema_snapshot")


@pytest.mark.django_db
def test_engine_command_does_not_send_or_overwrite_credentials(mocker):
    """回填请求不得携带 extra_info/凭证，写回时必须保留任务原有凭证。"""
    extra = {
        "custom_context": {"credentials": {"gw": {"bk_app_secret": "KEEP_ME"}}},
        "notify_config": {"notify_type": {"fail": []}},
    }
    task = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_v4_pipeline_tree(), extra_info=extra)
    mock_client = mocker.patch(
        "bkflow.task.management.commands.backfill_open_plugin_task_snapshots.InterfaceModuleClient"
    )
    snapshots = snapshot_payload()
    mock_client.return_value.build_open_plugin_snapshots.return_value = {
        "result": True,
        "data": {
            "changed": True,
            "reference_snapshot": snapshots["plugin_reference_snapshot"],
            "schema_snapshot": snapshots["plugin_schema_snapshot"],
        },
    }

    call_command("backfill_open_plugin_task_snapshots")

    payload = mock_client.return_value.build_open_plugin_snapshots.call_args[0][0]
    assert "extra_info" not in payload
    assert "KEEP_ME" not in json.dumps(payload)
    assert "bk_app_secret" not in json.dumps(payload)
    task.refresh_from_db()
    assert task.extra_info["custom_context"]["credentials"]["gw"]["bk_app_secret"] == "KEEP_ME"
    assert task.extra_info["notify_config"] == extra["notify_config"]
    assert task.extra_info["plugin_schema_snapshot"]["node1"]["plugin_id"] == "open_plugin_001"
