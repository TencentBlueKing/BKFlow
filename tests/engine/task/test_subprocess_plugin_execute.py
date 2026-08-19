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

from pipeline.core.data.base import DataObject

from bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0 import (
    SubprocessPluginService,
)
from bkflow.task.operations import OperationResult


class TestSubprocessPluginExecuteStartResult:
    def _execute_with_start_result(self, mocker, start_result):
        service = SubprocessPluginService()
        parent_task = mocker.Mock(id=11, creator="alice")
        child_task = mocker.Mock(id=99)
        data = DataObject(inputs={"subprocess": {}})
        parent_data = DataObject(inputs={"task_id": parent_task.id})
        template = {"data": {"pipeline_tree": {"constants": {}}}}
        subprocess = mocker.Mock()

        mocker.patch.object(service, "_get_subprocess_template", return_value=(template, subprocess))
        mocker.patch.object(service, "_process_subprocess_constants")
        mocker.patch.object(service, "_render_parent_parameters")
        mocker.patch.object(service, "_create_subprocess_task_instance", return_value=child_task)
        mocker.patch("bkflow.task.models.TaskInstance.objects.get", return_value=parent_task)
        mock_operation = mocker.patch("bkflow.task.operations.TaskOperation").return_value
        mock_operation.start.return_value = start_result

        result = service.plugin_execute(data, parent_data)
        return result, data, mock_operation

    def test_plugin_execute_fails_when_start_returns_false(self, mocker):
        """子流程启动预检失败时，节点应立即失败并写出预检信息。"""
        result, data, mock_operation = self._execute_with_start_result(
            mocker, OperationResult(result=False, message="开放插件来源 [sops] 未准入当前空间")
        )

        assert result is False
        assert data.get_one_of_outputs("task_id") == 99
        assert "未准入" in data.get_one_of_outputs("ex_data")
        mock_operation.start.assert_called_once_with(operator="alice")

    def test_plugin_execute_succeeds_when_start_returns_true(self, mocker):
        """子流程启动成功时，节点仍进入等待调度。"""
        result, data, mock_operation = self._execute_with_start_result(mocker, OperationResult(result=True, message=""))

        assert result is True
        assert data.get_one_of_outputs("task_id") == 99
        assert data.get_one_of_outputs("ex_data") is None
        mock_operation.start.assert_called_once_with(operator="alice")

    def test_plugin_execute_fails_before_create_when_snapshot_prepare_fails(self, mocker):
        """子流程快照构建失败时，不应产生半成品 TaskInstance。"""
        from bkflow.exceptions import ValidationError

        service = SubprocessPluginService()
        parent_task = mocker.Mock(id=11, creator="alice")
        data = DataObject(inputs={"subprocess": {}})
        parent_data = DataObject(inputs={"task_id": parent_task.id})
        template = {
            "data": {
                "pipeline_tree": {"constants": {}},
                "space_id": 1,
                "scope_type": "biz",
                "scope_value": "2",
                "notify_config": {},
            }
        }

        mocker.patch.object(service, "_get_subprocess_template", return_value=(template, mocker.Mock()))
        mocker.patch.object(service, "_process_subprocess_constants")
        mocker.patch.object(service, "_render_parent_parameters")
        create_mock = mocker.patch.object(service, "_create_subprocess_task_instance")
        mocker.patch("bkflow.task.models.TaskInstance.objects.get", return_value=parent_task)
        mocker.patch(
            "bkflow.pipeline_plugins.components.collections.subprocess_plugin.v1_0_0.prepare_engine_task_extra_info",
            side_effect=ValidationError("开放插件快照构建失败"),
        )

        result = service.plugin_execute(data, parent_data)

        assert result is False
        assert "快照" in data.get_one_of_outputs("ex_data")
        create_mock.assert_not_called()
