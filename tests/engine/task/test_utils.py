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
from bamboo_engine import states as bamboo_engine_states

from bkflow.task.utils import format_bamboo_engine_status, parse_node_timeout_configs
from bkflow.utils.pipeline import build_default_pipeline_tree


@pytest.mark.django_db(transaction=True)
class TestFormatBambooEngineStatus:
    """测试格式化 bamboo engine 状态"""

    def test_format_status(self):
        """测试格式化状态"""
        from django.utils import timezone

        # Format time
        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "started_time": timezone.now(),
            "archived_time": None,
            "children": {},
        }
        format_bamboo_engine_status(status_tree)
        assert "start_time" in status_tree

        # With children
        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "children": {"node1": {"state": bamboo_engine_states.FAILED, "children": {}}},
        }
        format_bamboo_engine_status(status_tree)
        assert status_tree["state"] == bamboo_engine_states.FAILED

        # Suspended
        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "children": {"node1": {"state": bamboo_engine_states.SUSPENDED, "children": {}}},
        }
        format_bamboo_engine_status(status_tree)
        assert status_tree["state"] == "NODE_SUSPENDED"


@pytest.mark.django_db(transaction=True)
class TestParseNodeTimeoutConfigs:
    """测试解析节点超时配置"""

    def test_parse_timeout_configs(self):
        """测试解析超时配置"""
        # Empty config
        pipeline_tree = build_default_pipeline_tree()
        result = parse_node_timeout_configs(pipeline_tree)
        assert result["result"] is True
        assert isinstance(result["data"], list)

        # With timeout
        activities = pipeline_tree.get("activities", {})
        if activities:
            first_activity_id = list(activities.keys())[0]
            activities[first_activity_id]["timeout_config"] = {
                "enable": True,
                "seconds": 300,
                "action": "forced_fail",
            }
            result = parse_node_timeout_configs(pipeline_tree)
            assert result["result"] is True
            assert len(result["data"]) > 0
            assert result["data"][0]["timeout"] == 300

            # Invalid timeout
            activities[first_activity_id]["timeout_config"]["seconds"] = "invalid"
            result = parse_node_timeout_configs(pipeline_tree)
            assert result["result"] is True
