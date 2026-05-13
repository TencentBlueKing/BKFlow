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

from types import SimpleNamespace

from bamboo_engine import states
from bamboo_engine.eri import ExecutionData
from bamboo_engine.handler import ExecuteResult
from bamboo_engine.handlers.service_activity import ServiceActivityHandler

from bkflow.task.engine_patches import (
    fail_service_activity_on_memory_error,
    patch_service_activity_handler,
)


class DummyRuntime:
    def __init__(self):
        self.execute_fail_calls = []
        self.state_calls = []
        self.execution_data_calls = []

    def node_execute_fail(self, root_pipeline_id, node_id):
        self.execute_fail_calls.append((root_pipeline_id, node_id))

    def set_state(self, **kwargs):
        self.state_calls.append(kwargs)

    def set_execution_data(self, **kwargs):
        self.execution_data_calls.append(kwargs)


def test_fail_service_activity_on_memory_error_records_compact_failure_data():
    runtime = DummyRuntime()
    handler = SimpleNamespace(runtime=runtime, node=SimpleNamespace(id="node-1"))
    process_info = SimpleNamespace(root_pipeline_id="root-1")

    result = fail_service_activity_on_memory_error(
        handler=handler,
        process_info=process_info,
        loop=1,
        inner_loop=2,
        version="version-1",
        recover_point=None,
        exc=MemoryError("worker memory exhausted"),
    )

    assert isinstance(result, ExecuteResult)
    assert result.should_sleep is True
    assert result.schedule_ready is False
    assert result.next_node_id is None
    assert runtime.execute_fail_calls == [("root-1", "node-1")]
    assert runtime.state_calls == [
        {
            "node_id": "node-1",
            "version": "version-1",
            "to_state": states.FAILED,
            "set_archive_time": True,
            "ignore_boring_set": False,
        }
    ]

    execution_data = runtime.execution_data_calls[0]["data"]
    assert isinstance(execution_data, ExecutionData)
    assert execution_data.inputs == {}
    assert execution_data.outputs["_result"] is False
    assert execution_data.outputs["_loop"] == 1
    assert execution_data.outputs["_inner_loop"] == 2
    assert "执行数据保存失败" in execution_data.outputs["ex_data"]
    assert "节点输入/输出数据过大" in execution_data.outputs["ex_data"]
    assert "MemoryError" in execution_data.outputs["ex_data"]


def test_patch_service_activity_handler_converts_memory_error(monkeypatch):
    def raise_memory_error(self, process_info, loop, inner_loop, version, recover_point=None):
        raise MemoryError("too large")

    runtime = DummyRuntime()
    handler = SimpleNamespace(runtime=runtime, node=SimpleNamespace(id="node-1"))
    process_info = SimpleNamespace(root_pipeline_id="root-1")

    monkeypatch.setattr(ServiceActivityHandler, "execute", raise_memory_error)
    patch_service_activity_handler()

    result = ServiceActivityHandler.execute(
        handler,
        process_info=process_info,
        loop=1,
        inner_loop=1,
        version="version-1",
    )

    assert result.schedule_ready is False
    assert runtime.state_calls[0]["to_state"] == states.FAILED
