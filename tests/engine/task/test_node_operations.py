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

from datetime import timedelta
from unittest import mock

import pytest
from bamboo_engine import states as bamboo_engine_states
from bamboo_engine.api import EngineAPIResult
from django.utils import timezone

from bkflow.task.models import OpenPluginRunCallbackRef, TaskInstance
from bkflow.task.open_plugin_callback import (
    callback_token_digest,
    issue_open_plugin_callback_token,
)
from bkflow.task.operations import OperationResult, TaskNodeOperation
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestTaskNodeOperation:
    """测试 TaskNodeOperation 节点操作"""

    def test_open_plugin_callback_ref_supports_runtime_node_version_length(self):
        """真实运行时节点版本为 v 加 32 位十六进制串，存储字段不得截断。"""

        node_version_field = OpenPluginRunCallbackRef._meta.get_field("node_version")

        assert node_version_field.max_length >= len("v27b15e4ff8ec4a238e479331c5140cb5")

    def _create_task_instance_with_node(self):
        task_instance = TaskInstance.objects.create_instance(space_id=1, pipeline_tree=build_default_pipeline_tree())
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")
        return task_instance, node_ids[0]

    def _create_open_plugin_callback_ref(
        self,
        task_instance,
        node_id,
        token,
        node_version="v4.0.0",
        open_plugin_run_id="run-001",
        consumed_at=None,
    ):
        return OpenPluginRunCallbackRef.objects.create(
            task_id=task_instance.id,
            node_id=node_id,
            node_version=node_version,
            client_request_id=f"task-{task_instance.id}-node-{node_id}-attempt-1",
            open_plugin_run_id=open_plugin_run_id,
            callback_token_digest=callback_token_digest(token),
            callback_expire_at=timezone.now() + timedelta(hours=1),
            plugin_source="builtin",
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_version="1.2.0",
            cancel_url="https://bk-sops.example/open-plugin-runs/run-001/cancel",
            credential_key="default",
            consumed_at=consumed_at,
        )

    def test_upsert_open_plugin_callback_ref(self):
        from bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0 import (
            UniformAPIService,
        )

        token, expire_at = issue_open_plugin_callback_token(
            task_id=1,
            node_id="node_a",
            client_request_id="task-1-node-node_a-attempt-1",
            node_version="v4.0.0",
        )

        UniformAPIService._upsert_open_plugin_callback_ref(
            task_id=1,
            node_id="node_a",
            node_version="v4.0.0",
            client_request_id="task-1-node-node_a-attempt-1",
            open_plugin_run_id="run-001",
            callback_token=token,
            callback_expire_at=expire_at,
            plugin_source="builtin",
            source_key="sops",
            plugin_id="open_plugin_001",
            plugin_version="1.2.0",
            cancel_url="https://bk-sops.example/open-plugin-runs/run-001/cancel",
            credential_key="default",
        )

        callback_ref = OpenPluginRunCallbackRef.objects.get(client_request_id="task-1-node-node_a-attempt-1")
        assert callback_ref.open_plugin_run_id == "run-001"
        assert callback_ref.callback_token_digest == callback_token_digest(token)
        assert callback_ref.plugin_id == "open_plugin_001"
        assert callback_ref.source_key == "sops"
        assert callback_ref.cancel_url == "https://bk-sops.example/open-plugin-runs/run-001/cancel"
        assert callback_ref.credential_key == "default"

    def test_retry_node(self, mocker):
        """测试重试节点"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.get_data", return_value=EngineAPIResult(result=True, data={}, message="success")
        )
        mocker.patch("bamboo_engine.api.retry_node", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.retry(operator="test_operator")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_skip_node(self, mocker):
        """测试跳过节点"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch("bamboo_engine.api.skip_node", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.skip(operator="test_operator")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_callback_node(self, mocker):
        """测试节点回调"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)

        mock_state = type("State", (), {"version": 1})()
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_state", return_value=mock_state)
        mocker.patch("bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success"))

        result = node_operation.callback(operator="test_operator", data={"key": "value"})
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_callback_keeps_legacy_path_when_business_field_collides(self, mocker):
        """普通回调即使携带 open_plugin_run_id，没有 _callback_token 仍走 bamboo callback。"""
        task_instance, node_id = self._create_task_instance_with_node()
        node_operation = TaskNodeOperation(task_instance, node_id)
        mock_state = type("State", (), {"version": 1})()
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_state", return_value=mock_state)
        callback_api = mocker.patch(
            "bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success")
        )
        payload = {"open_plugin_run_id": "biz-001", "status": "success", "data": {"result": "done"}}

        result = node_operation.callback(operator="test_operator", data=payload)

        assert result.result is True
        callback_api.assert_called_once_with(runtime=mock.ANY, node_id=node_id, version=1, data=payload)

    def test_open_plugin_callback_token_ttl_covers_max_node_timeout(self, settings):
        """回调 token 默认有效期对齐节点最长执行时间，避免纯回调插件中途过期。"""
        settings.MAX_NODE_EXECUTE_TIMEOUT = 60 * 60 * 24
        settings.OPEN_PLUGIN_CALLBACK_TOKEN_TTL = settings.MAX_NODE_EXECUTE_TIMEOUT
        issued_at = timezone.now()

        _, expire_at = issue_open_plugin_callback_token(task_id=1, node_id="node_a", client_request_id="cid-1")

        assert expire_at - issued_at >= timedelta(seconds=settings.MAX_NODE_EXECUTE_TIMEOUT - 5)

    def test_open_plugin_callback_accepts_valid_payload(self, mocker):
        """开放插件回调由 engine 校验 token/ref 后再回调 bamboo engine。"""

        task_instance, node_id = self._create_task_instance_with_node()
        node_version = "v4.0.0"
        client_request_id = f"task-{task_instance.id}-node-{node_id}-attempt-1"
        token, _ = issue_open_plugin_callback_token(
            task_id=task_instance.id,
            node_id=node_id,
            client_request_id=client_request_id,
            node_version=node_version,
        )
        callback_ref = self._create_open_plugin_callback_ref(
            task_instance=task_instance, node_id=node_id, token=token, node_version=node_version
        )

        mock_state = type("State", (), {"name": bamboo_engine_states.RUNNING, "version": node_version})()
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_state", return_value=mock_state)
        callback_api = mocker.patch(
            "bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success")
        )

        result = TaskNodeOperation(task_instance, node_id).callback(
            operator="system",
            data={
                "open_plugin_run_id": "run-001",
                "status": "SUCCEEDED",
                "outputs": {"job_instance_id": 1001},
                "_callback_token": token,
            },
        )

        assert result.result is True
        callback_api.assert_called_once_with(
            runtime=mock.ANY,
            node_id=node_id,
            version=node_version,
            data={
                "open_plugin_run_id": "run-001",
                "status": "SUCCEEDED",
                "outputs": {"job_instance_id": 1001},
            },
        )
        callback_ref.refresh_from_db()
        assert callback_ref.consumed_at is not None

    def test_open_plugin_callback_rejects_invalid_token(self, mocker):
        """开放插件回调 token 无效时，engine 不触发 bamboo callback。"""

        task_instance, node_id = self._create_task_instance_with_node()
        node_version = "v4.0.0"
        client_request_id = f"task-{task_instance.id}-node-{node_id}-attempt-1"
        token, _ = issue_open_plugin_callback_token(
            task_id=task_instance.id,
            node_id=node_id,
            client_request_id=client_request_id,
            node_version=node_version,
        )
        self._create_open_plugin_callback_ref(
            task_instance=task_instance, node_id=node_id, token=token, node_version=node_version
        )
        callback_api = mocker.patch(
            "bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success")
        )

        result = TaskNodeOperation(task_instance, node_id).callback(
            operator="system",
            data={
                "open_plugin_run_id": "run-001",
                "status": "SUCCEEDED",
                "_callback_token": "invalid-token",
            },
        )

        assert result.result is False
        assert "callback token" in result.message
        callback_api.assert_not_called()

    def test_open_plugin_callback_duplicate_request_is_idempotent(self, mocker):
        """已消费过的开放插件回调在 engine 侧幂等返回成功。"""

        task_instance, node_id = self._create_task_instance_with_node()
        node_version = "v4.0.0"
        client_request_id = f"task-{task_instance.id}-node-{node_id}-attempt-1"
        token, _ = issue_open_plugin_callback_token(
            task_id=task_instance.id,
            node_id=node_id,
            client_request_id=client_request_id,
            node_version=node_version,
        )
        self._create_open_plugin_callback_ref(
            task_instance=task_instance,
            node_id=node_id,
            token=token,
            node_version=node_version,
            consumed_at=timezone.now(),
        )
        callback_api = mocker.patch(
            "bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success")
        )

        result = TaskNodeOperation(task_instance, node_id).callback(
            operator="system",
            data={
                "open_plugin_run_id": "run-001",
                "status": "SUCCEEDED",
                "_callback_token": token,
            },
        )

        assert result.result is True
        assert "already consumed" in result.message
        callback_api.assert_not_called()

    def test_open_plugin_callback_terminal_node_is_swallowed(self, mocker):
        """节点已离开运行态时，engine 消费回调但不再触发 bamboo callback。"""

        task_instance, node_id = self._create_task_instance_with_node()
        node_version = "v4.0.0"
        client_request_id = f"task-{task_instance.id}-node-{node_id}-attempt-1"
        token, _ = issue_open_plugin_callback_token(
            task_id=task_instance.id,
            node_id=node_id,
            client_request_id=client_request_id,
            node_version=node_version,
        )
        callback_ref = self._create_open_plugin_callback_ref(
            task_instance=task_instance, node_id=node_id, token=token, node_version=node_version
        )

        mock_state = type("State", (), {"name": bamboo_engine_states.FINISHED, "version": node_version})()
        mocker.patch("pipeline.eri.runtime.BambooDjangoRuntime.get_state", return_value=mock_state)
        callback_api = mocker.patch(
            "bamboo_engine.api.callback", return_value=EngineAPIResult(result=True, message="success")
        )

        result = TaskNodeOperation(task_instance, node_id).callback(
            operator="system",
            data={
                "open_plugin_run_id": "run-001",
                "status": "SUCCEEDED",
                "_callback_token": token,
            },
        )

        assert result.result is True
        assert "terminal state" in result.message
        callback_api.assert_not_called()
        callback_ref.refresh_from_db()
        assert callback_ref.consumed_at is not None

    def test_skip_exg(self, mocker):
        """测试跳过排他网关"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.skip_exclusive_gateway",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.skip_exg(operator="test_operator", flow_id="flow_123")
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_skip_cpg(self, mocker):
        """测试跳过条件并行网关"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.skip_conditional_parallel_gateway",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.skip_cpg(
            operator="test_operator", flow_ids=["flow_1", "flow_2"], converge_gateway_id="gateway_123"
        )
        assert isinstance(result, OperationResult)
        assert result.result is True

    def test_forced_fail(self, mocker):
        """测试强制失败"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id,
            pipeline_tree=build_default_pipeline_tree(),
            create_method="DEBUG",
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        suppress_failure_side_effects = mocker.patch(
            "bkflow.task.operations.suppress_node_failure_side_effects", create=True
        )
        cancel_open_plugin_runs = mocker.patch("bkflow.task.celery.tasks.cancel_open_plugin_runs.delay")
        forced_fail_activity = mocker.patch(
            "bamboo_engine.api.forced_fail_activity",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.forced_fail(
            operator="test_operator",
            ex_data="test error",
            suppress_failure_side_effects=True,
        )
        assert isinstance(result, OperationResult)
        assert result.result is True
        suppress_failure_side_effects.assert_called_once_with(task_instance.instance_id, node_id)
        forced_fail_activity.assert_called_once_with(
            runtime=node_operation.runtime,
            node_id=node_id,
            ex_data="test error",
            send_post_set_state_signal=True,
        )
        cancel_open_plugin_runs.assert_called_once_with(
            task_id=task_instance.id, node_id=node_id, operator="test_operator"
        )

    def test_forced_fail_on_mock_task_does_not_suppress_side_effects(self, mocker):
        """存量 MOCK 任务 forced_fail 不屏蔽失败副作用，但仍取消开放插件。"""
        task_instance = TaskInstance.objects.create_instance(
            space_id=1,
            pipeline_tree=build_default_pipeline_tree(),
            create_method="MOCK",
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        suppress_failure_side_effects = mocker.patch(
            "bkflow.task.operations.suppress_node_failure_side_effects", create=True
        )
        cancel_open_plugin_runs = mocker.patch("bkflow.task.celery.tasks.cancel_open_plugin_runs.delay")
        mocker.patch(
            "bamboo_engine.api.forced_fail_activity",
            return_value=EngineAPIResult(result=True, message="success"),
        )

        result = node_operation.forced_fail(
            operator="test_operator",
            ex_data="test error",
            suppress_failure_side_effects=True,
        )

        assert result.result is True
        suppress_failure_side_effects.assert_not_called()
        cancel_open_plugin_runs.assert_called_once_with(
            task_id=task_instance.id, node_id=node_id, operator="test_operator"
        )

    def test_get_node_detail_not_executed(self, mocker):
        """测试获取未执行节点详情"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)

        mocker.patch(
            "bamboo_engine.api.get_children_states",
            return_value=EngineAPIResult(result=True, data={}, message="success"),
        )

        result = node_operation.get_node_detail()
        assert isinstance(result, OperationResult)
        assert result.result is True
        assert result.data["state"] == bamboo_engine_states.READY

    def test_get_outputs(self, mocker):
        """测试获取节点输出"""
        space_id = 1
        task_instance = TaskInstance.objects.create_instance(
            space_id=space_id, pipeline_tree=build_default_pipeline_tree()
        )
        task_instance.calculate_tree_info()
        node_ids = list(task_instance.node_id_set)
        if not node_ids:
            pytest.skip("No nodes in pipeline tree")

        node_id = node_ids[0]
        node_operation = TaskNodeOperation(task_instance, node_id)
        mocker.patch(
            "bamboo_engine.api.get_execution_data_outputs",
            return_value=EngineAPIResult(result=True, data={"output1": "value1"}, message="success"),
        )

        result = node_operation.get_outputs()
        assert isinstance(result, OperationResult)
        assert result.result is True
