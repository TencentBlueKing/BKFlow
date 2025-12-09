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

    def test_format_status_time(self):
        """测试格式化状态时间"""
        from django.utils import timezone

        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "started_time": timezone.now(),
            "archived_time": None,
            "children": {},
        }

        format_bamboo_engine_status(status_tree)

        assert "start_time" in status_tree
        assert "finish_time" in status_tree
        assert "elapsed_time" in status_tree

    def test_format_status_with_children(self):
        """测试格式化带子节点的状态"""
        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "children": {
                "node1": {
                    "state": bamboo_engine_states.FAILED,
                    "children": {},
                }
            },
        }

        format_bamboo_engine_status(status_tree)

        assert status_tree["state"] == bamboo_engine_states.FAILED
        assert "start_time" in status_tree["children"]["node1"]

    def test_format_status_suspended(self):
        """测试格式化暂停状态"""
        status_tree = {
            "state": bamboo_engine_states.RUNNING,
            "children": {
                "node1": {
                    "state": bamboo_engine_states.SUSPENDED,
                    "children": {},
                }
            },
        }

        format_bamboo_engine_status(status_tree)

        assert status_tree["state"] == "NODE_SUSPENDED"


@pytest.mark.django_db(transaction=True)
class TestParseNodeTimeoutConfigs:
    """测试解析节点超时配置"""

    def test_parse_timeout_configs_empty(self):
        """测试解析空配置"""
        pipeline_tree = build_default_pipeline_tree()
        result = parse_node_timeout_configs(pipeline_tree)

        assert result["result"] is True
        assert isinstance(result["data"], list)

    def test_parse_timeout_configs_with_timeout(self):
        """测试解析带超时配置的节点"""
        pipeline_tree = build_default_pipeline_tree()
        # 添加超时配置
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
        assert result["data"][0]["action"] == "forced_fail"

    def test_parse_timeout_configs_invalid_timeout(self):
        """测试解析无效的超时配置"""
        pipeline_tree = build_default_pipeline_tree()
        activities = pipeline_tree.get("activities", {})
        if activities:
            first_activity_id = list(activities.keys())[0]
            activities[first_activity_id]["timeout_config"] = {
                "enable": True,
                "seconds": "invalid",  # 无效的超时时间
                "action": "forced_fail",
            }

        result = parse_node_timeout_configs(pipeline_tree)

        # 无效配置会被忽略，但不会导致解析失败
        assert result["result"] is True
