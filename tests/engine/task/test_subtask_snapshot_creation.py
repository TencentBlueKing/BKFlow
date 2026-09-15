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

# 验证子流程和子画布的快照依赖、重复创建与事务边界。

from copy import deepcopy

import pytest
from django.db import IntegrityError, connection

from bkflow.constants import TaskTriggerMethod
from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.exceptions import ValidationError
from bkflow.pipeline_plugins.components.collections.subcanvas_plugin.v1_0_0 import (
    SubcanvasPluginService,
)
from bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0 import (
    SubprocessPluginService,
)
from bkflow.task.models import (
    TaskExecutionSnapshot,
    TaskFlowRelation,
    TaskInstance,
    TaskOperationRecord,
    TaskSnapshot,
)
from bkflow.utils.pipeline import build_default_pipeline_tree

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(params=[(False, {}), (True, {"tenant_id": "tenant-a"})], ids=["single", "multi"])
def tenant_context(request, settings):
    settings.ENABLE_MULTI_TENANT_MODE = request.param[0]
    return request.param[1]


@pytest.fixture(params=[SubprocessPluginService, SubcanvasPluginService])
def subtask_context(request, tenant_context):
    """在单、多租户模式下为两个调用入口创建真实父任务。"""
    service = request.param()
    service.id = "parent_node"
    service.version = "v1.0.0"
    trigger = (
        TaskTriggerMethod.subprocess.name
        if request.param is SubprocessPluginService
        else TaskTriggerMethod.sub_canvas.name
    )
    parent = TaskInstance.objects.create_instance(
        name="parent",
        creator="alice",
        space_id=1,
        scope_type="biz",
        scope_value="2",
        pipeline_tree=build_default_pipeline_tree(),
        **tenant_context,
    )
    return service, parent, trigger


def create_child(context, component):
    """通过共享创建入口写入真实子任务。"""
    service, parent, trigger = context
    tree = build_default_pipeline_tree()
    activity = next(iter(tree["activities"].values()))
    activity.update(type="ServiceActivity", component=deepcopy(component))
    return service._create_subprocess_task_instance(
        "child",
        tree,
        parent,
        trigger,
        template_id=123 if trigger == TaskTriggerMethod.subprocess.name else None,
        notify_config={"notify_type": {"fail": ["weixin"]}},
    )


def task_record_counts():
    """同时检查任务、关系、流水及两类快照的残留。"""
    return tuple(
        model.objects.count()
        for model in (TaskInstance, TaskFlowRelation, TaskOperationRecord, TaskSnapshot, TaskExecutionSnapshot)
    )


@pytest.mark.parametrize(
    "component",
    [
        {"code": "sleep_timer", "version": "v1.0.0", "data": {}},
        {"code": "uniform_api", "version": "v2.0.0", "data": {}},
        {"code": "uniform_api", "version": "v3.0.0", "data": {}},
    ],
)
def test_plain_subtask_has_no_snapshot_request(subtask_context, mocker, component):
    """普通节点及 uniform_api V2/V3 在 Interface 不可用时仍可创建。"""
    prepare = mocker.patch.object(
        InterfaceModuleClient, "prepare_task_extra_info", side_effect=AssertionError("network")
    )
    child = create_child(subtask_context, component)

    prepare.assert_not_called()
    child.refresh_from_db()
    assert child.tenant_id == subtask_context[1].tenant_id
    assert child.extra_info == {"notify_config": {"notify_type": {"fail": ["weixin"]}}}
    assert task_record_counts() == (2, 1, 1, 2, 2)
    relation = TaskFlowRelation.objects.get(task_id=child.id)
    assert relation.parent_task_id == subtask_context[1].id
    assert relation.root_task_id == subtask_context[1].id
    assert relation.extra_info["trigger_method"] == subtask_context[2]


@pytest.mark.parametrize(
    "component",
    [
        {"code": "uniform_api", "version": "v4.0.0", "data": {}},
        {"code": "uniform_api", "data": {"uniform_api_plugin_id": {"value": "plugin1"}}},
        {
            "code": "uniform_api",
            "version": "1.2.0",
            "api_meta": {
                "versions": ["1.2.0"],
                "meta_url_template": "http://plugin.test/meta/{version}",
            },
        },
    ],
)
def test_open_subtask_retries_before_atomic_creation(subtask_context, mocker, component):
    """开放插件兼容标识均准备快照，瞬时错误恢复后只创建一份任务及关联。"""
    mocker.patch("bkflow.contrib.api.collections.interface.time.sleep")
    attempts = []

    def prepare(**kwargs):
        assert not connection.in_atomic_block
        assert task_record_counts() == (1, 0, 0, 1, 1)
        attempts.append(deepcopy(kwargs["data"]))
        if len(attempts) == 1:
            return {"result": False, "error_type": "http", "status_code": 502, "retryable": True}
        assert attempts[0] == attempts[1]
        assert kwargs["data"]["scope_type"] == "biz"
        assert kwargs["data"]["scope_id"] == "2"
        assert kwargs["data"]["username"] == "alice"
        extra = deepcopy(kwargs["data"]["extra_info"])
        extra.update(plugin_reference_snapshot=[{"plugin_id": "plugin1"}], plugin_schema_snapshot={"node1": {}})
        return {"result": True, "data": {"extra_info": extra}}

    prepare_request = mocker.patch.object(InterfaceModuleClient, "_request", side_effect=prepare)
    child = create_child(subtask_context, component)

    assert prepare_request.call_count == 2
    child.refresh_from_db()
    assert child.tenant_id == subtask_context[1].tenant_id
    assert task_record_counts() == (2, 1, 1, 2, 2)
    assert child.extra_info["plugin_reference_snapshot"] == [{"plugin_id": "plugin1"}]
    assert child.extra_info["plugin_schema_snapshot"] == {"node1": {}}
    assert child.extra_info["notify_config"] == {"notify_type": {"fail": ["weixin"]}}


@pytest.mark.parametrize(
    "failure, attempts",
    [
        ({"result": False, "error_type": "http", "status_code": 502, "retryable": True}, 3),
        ({"result": False, "message": "插件在当前空间未开放"}, 1),
    ],
)
def test_failed_snapshot_does_not_create_any_task_records(subtask_context, mocker, failure, attempts):
    """快照准备持续失败或业务校验拒绝时，数据库不产生半成品。"""
    mocker.patch("bkflow.contrib.api.collections.interface.time.sleep")
    request = mocker.patch.object(InterfaceModuleClient, "_request", return_value=failure)
    before = task_record_counts()

    with pytest.raises(ValidationError, match="生成开放插件快照失败"):
        create_child(subtask_context, {"code": "uniform_api", "version": "v4.0.0", "data": {}})

    assert request.call_count == attempts
    assert task_record_counts() == before


def test_relation_failure_rolls_back_subtask_and_snapshots(subtask_context, mocker):
    """关联写入失败时，任务、流水和快照仍在同一个事务中回滚。"""
    before = task_record_counts()

    def fail_relation(**kwargs):
        assert connection.in_atomic_block
        assert TaskInstance.objects.count() == 2
        assert TaskOperationRecord.objects.count() == 1
        raise IntegrityError("injected relation failure")

    mocker.patch.object(TaskFlowRelation.objects, "create", side_effect=fail_relation)
    with pytest.raises(IntegrityError, match="injected relation failure"):
        create_child(subtask_context, {"code": "sleep_timer", "version": "v1.0.0", "data": {}})

    assert task_record_counts() == before
