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
from unittest import mock

import pytest

from bkflow.interface.task.utils import StageConstantHandler, StageJobStateHandler


class TestStageJobStateHandler:
    """Test StageJobStateHandler class"""

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_handler_initialization(self, mock_client_class):
        """Test handler initialization"""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        handler = StageJobStateHandler(space_id=1, is_superuser=True)
        assert handler.space_id == 1
        assert handler.is_superuser is True
        assert handler.client is not None
        mock_client_class.assert_called_once_with(space_id=1, from_superuser=True)

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_get_task_data(self, mock_client_class):
        """Test task data retrieval with success, missing data, and exception"""
        # Success
        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {"data": {"pipeline_tree": {"activities": {}, "gateways": {}}}}
        mock_client_class.return_value = mock_client
        handler = StageJobStateHandler(space_id=1)
        result = handler.get_task_data("task_123")
        assert "task_detail" in result
        assert result["pipeline_tree"]["activities"] == {}

        # Missing data
        mock_client.get_task_detail.return_value = {}
        result = handler.get_task_data("task_123")
        assert result["pipeline_tree"] == {}

        # Exception
        mock_client.get_task_detail.side_effect = Exception("API Error")
        with pytest.raises(Exception) as exc_info:
            handler.get_task_data("task_123")
        assert "API Error" in str(exc_info.value)

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_get_node_states(self, mock_client_class):
        """Test node states retrieval with success, missing data, and exception"""
        # Success
        mock_client = mock.Mock()
        mock_client.get_task_states.return_value = {
            "data": {"children": {"node1": {"state": "FINISHED"}, "node2": {"state": "RUNNING"}}}
        }
        mock_client_class.return_value = mock_client
        handler = StageJobStateHandler(space_id=1)
        result = handler.get_node_states("task_123")
        assert result["node1"]["state"] == "FINISHED"
        assert result["node2"]["state"] == "RUNNING"

        # Missing data
        mock_client.get_task_states.return_value = {}
        result = handler.get_node_states("task_123")
        assert result == {}

        # Exception
        mock_client.get_task_states.side_effect = Exception("Network Error")
        result = handler.get_node_states("task_123")
        assert result == {}

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_build_template_task_mapping(self, mock_client_class):
        """Test building template to task node ID mapping"""
        mock_client_class.return_value = mock.Mock()
        handler = StageJobStateHandler(space_id=1)
        # With activities
        activities = {
            "task_node_1": {"template_node_id": "template_1", "name": "Activity 1"},
            "task_node_2": {"template_node_id": "template_2", "name": "Activity 2"},
            "task_node_3": {"name": "Activity 3"},  # No template_node_id
        }
        result = handler.build_template_task_mapping(activities)
        assert result == {"template_1": "task_node_1", "template_2": "task_node_2"}
        assert "template_3" not in result

        # Empty activities
        result = handler.build_template_task_mapping({})
        assert result == {}

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_build_node_info_map(self, mock_client_class):
        """Test building node information map"""
        mock_client_class.return_value = mock.Mock()
        handler = StageJobStateHandler(space_id=1)
        template_to_task_id = {"template_1": "task_node_1", "template_2": "task_node_2"}
        node_states = {
            "task_node_1": {
                "state": "FINISHED",
                "start_time": "2024-01-01 00:00:00",
                "finish_time": "2024-01-01 00:01:00",
                "loop": 1,
                "retry": 0,
                "skip": False,
                "error_ignorable": False,
                "error_ignored": False,
            },
            "task_node_2": {
                "state": "RUNNING",
                "start_time": "2024-01-01 00:02:00",
                "finish_time": "",
                "loop": 2,
                "retry": 1,
                "skip": False,
                "error_ignorable": True,
                "error_ignored": False,
            },
        }

        result = handler.build_node_info_map(template_to_task_id, node_states)

        assert "template_1" in result
        assert result["template_1"]["state"] == "FINISHED"
        assert result["template_1"]["loop"] == 1
        assert result["template_2"]["state"] == "RUNNING"
        assert result["template_2"]["retry"] == 1

    def test_calculate_job_state(self):
        """Test job state calculation with various scenarios"""
        assert StageJobStateHandler.calculate_job_state([]) == "READY"
        assert StageJobStateHandler.calculate_job_state(["FINISHED", "RUNNING", "FAILED"]) == "FAILED"
        assert StageJobStateHandler.calculate_job_state(["FINISHED", "RUNNING", "READY"]) == "RUNNING"
        assert StageJobStateHandler.calculate_job_state(["READY", "READY", "READY"]) == "READY"
        assert StageJobStateHandler.calculate_job_state(["FINISHED", "FINISHED", "FINISHED"]) == "FINISHED"
        assert StageJobStateHandler.calculate_job_state(["FINISHED", "READY", "FINISHED"]) == "RUNNING"

    def test_calculate_stage_state(self):
        """Test stage state calculation with various scenarios"""
        assert StageJobStateHandler.calculate_stage_state([]) == "READY"
        assert StageJobStateHandler.calculate_stage_state(["FINISHED", "RUNNING", "FAILED"]) == "FAILED"
        assert StageJobStateHandler.calculate_stage_state(["FINISHED", "RUNNING", "READY"]) == "RUNNING"
        assert StageJobStateHandler.calculate_stage_state(["READY", "READY", "READY"]) == "READY"
        assert StageJobStateHandler.calculate_stage_state(["FINISHED", "FINISHED", "FINISHED"]) == "FINISHED"

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_update_states(self, mock_client_class):
        """Test updating states in stage structure"""
        mock_client_class.return_value = mock.Mock()
        handler = StageJobStateHandler(space_id=1)

        stage_struct = [
            {"id": "stage1", "jobs": [{"id": "job1", "nodes": [{"id": "template_1"}, {"id": "template_2"}]}]}
        ]

        node_info_map = {
            "template_1": {
                "state": "FINISHED",
                "start_time": "2024-01-01 00:00:00",
                "finish_time": "2024-01-01 00:01:00",
                "loop": 1,
                "retry": 0,
                "skip": False,
                "error_ignorable": False,
                "error_ignored": False,
            },
            "template_2": {
                "state": "FINISHED",
                "start_time": "2024-01-01 00:00:00",
                "finish_time": "2024-01-01 00:01:00",
                "loop": 1,
                "retry": 0,
                "skip": False,
                "error_ignorable": False,
                "error_ignored": False,
            },
        }

        handler.update_states(stage_struct, node_info_map)

        # Check node states are updated
        assert stage_struct[0]["jobs"][0]["nodes"][0]["state"] == "FINISHED"
        assert stage_struct[0]["jobs"][0]["nodes"][1]["state"] == "FINISHED"

        # Check job state
        assert stage_struct[0]["jobs"][0]["state"] == "FINISHED"

        # Check stage state
        assert stage_struct[0]["state"] == "FINISHED"

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_process_complete_workflow(self, mock_client_class):
        """Test complete process workflow"""
        mock_client = mock.Mock()
        mock_client.get_task_detail.return_value = {
            "data": {
                "pipeline_tree": {
                    "activities": {"task_node_1": {"template_node_id": "template_1"}},
                    "stage_canvas_data": [{"id": "stage1", "jobs": [{"id": "job1", "nodes": [{"id": "template_1"}]}]}],
                }
            }
        }
        mock_client.get_task_states.return_value = {
            "data": {
                "children": {
                    "task_node_1": {
                        "state": "FINISHED",
                        "start_time": "2024-01-01 00:00:00",
                        "finish_time": "2024-01-01 00:01:00",
                        "loop": 1,
                        "retry": 0,
                        "skip": False,
                        "error_ignorable": False,
                        "error_ignored": False,
                    }
                }
            }
        }
        mock_client_class.return_value = mock_client

        handler = StageJobStateHandler(space_id=1)
        result = handler.process("task_123")

        assert len(result) == 1
        assert result[0]["state"] == "FINISHED"
        assert result[0]["jobs"][0]["state"] == "FINISHED"


class TestStageConstantHandler:
    """Test StageConstantHandler class"""

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_handler_initialization(self, mock_client_class):
        """Test handler initialization"""
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client

        handler = StageConstantHandler(space_id=1, is_superuser=True)
        assert handler.space_id == 1
        assert handler.is_superuser is True
        assert handler.client is not None
        mock_client_class.assert_called_once_with(space_id=1, from_superuser=True)

    @mock.patch("bkflow.interface.task.utils.TaskComponentClient")
    def test_process_success(self, mock_client_class):
        """Test successful constant rendering"""
        mock_client = mock.Mock()
        mock_client.render_context_with_node_outputs.return_value = {
            "const1": "rendered_value_1",
            "const2": "rendered_value_2",
        }
        mock_client_class.return_value = mock_client

        handler = StageConstantHandler(space_id=1)
        result = handler.process(
            task_id="task_123",
            node_ids=["node1", "node2"],
            stage_constants=[
                {"key": "const1", "value": "${node1.output}"},
                {"key": "const2", "value": "${node2.output}"},
            ],
        )

        assert result["const1"] == "rendered_value_1"
        assert result["const2"] == "rendered_value_2"

        mock_client.render_context_with_node_outputs.assert_called_once_with(
            "task_123", data={"node_ids": ["node1", "node2"], "to_render_constants": ["const1", "const2"]}
        )
