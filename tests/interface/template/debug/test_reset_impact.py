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

from bkflow.template.debug.dependency import compute_tree_fingerprint
from bkflow.template.debug.service import DebugService
from bkflow.template.models import DebugContext

TREE_V1 = {
    "activities": {
        "A": {
            "id": "A",
            "type": "ServiceActivity",
            "optional": True,
            "component": {"code": "t", "data": {"x": {"hook": False, "value": "1"}}},
        },
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "optional": True,
            "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}},
        },
    },
    "flows": {"f1": {"id": "f1", "source": "A", "target": "B"}},
    "gateways": {},
    "constants": {
        "${g1}": {
            "key": "${g1}",
            "name": "g1",
            "show_type": "hide",
            "value": "",
            "source_type": "component_outputs",
            "source_info": {"A": ["k1"]},
            "custom_type": "",
            "source_tag": "",
        }
    },
}


@pytest.mark.django_db
class TestResetImpact:
    def test_node_config_change_propagates_downstream(self):
        DebugContext.objects.create(template_id=1, space_id=10, tree_fingerprint=compute_tree_fingerprint(TREE_V1))
        # A 配置变更
        tree_v2 = {
            **TREE_V1,
            "activities": {
                "A": {
                    "id": "A",
                    "type": "ServiceActivity",
                    "optional": True,
                    "component": {"code": "t", "data": {"x": {"hook": False, "value": "CHANGED"}}},
                },
                "B": TREE_V1["activities"]["B"],
            },
        }
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=tree_v2)
        result = svc.reset_impact()
        assert set(result["reset_node_ids"]) == {"A", "B"}
        assert "A" in result["reasons"]

    def test_no_change_returns_empty(self):
        DebugContext.objects.create(template_id=1, space_id=10, tree_fingerprint=compute_tree_fingerprint(TREE_V1))
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE_V1)
        result = svc.reset_impact()
        assert result["reset_node_ids"] == []

    def test_data_flow_only_propagation(self):
        """仅靠数据流（无控制流连线）也能把下游消费者纳入闭包。"""
        tree_v1 = {
            "activities": {
                "A": {
                    "id": "A",
                    "type": "ServiceActivity",
                    "optional": True,
                    "component": {"code": "t", "data": {"x": {"hook": False, "value": "1"}}},
                },
                "B": {
                    "id": "B",
                    "type": "ServiceActivity",
                    "optional": True,
                    "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}},
                },
            },
            "flows": {},  # 故意不连控制流，B 仅通过 ${g1} 数据依赖 A
            "gateways": {},
            "constants": TREE_V1["constants"],
        }
        DebugContext.objects.create(template_id=2, space_id=10, tree_fingerprint=compute_tree_fingerprint(tree_v1))
        tree_v2 = {
            **tree_v1,
            "activities": {
                "A": {
                    "id": "A",
                    "type": "ServiceActivity",
                    "optional": True,
                    "component": {"code": "t", "data": {"x": {"hook": False, "value": "CHANGED"}}},
                },
                "B": tree_v1["activities"]["B"],
            },
        }
        svc = DebugService(template_id=2, space_id=10, pipeline_tree=tree_v2)
        result = svc.reset_impact()
        assert set(result["reset_node_ids"]) == {"A", "B"}

    def test_removed_node_triggers_conservative_reset(self):
        """删除节点后，无法从新图获知其下游，保守地重置当前全部节点。"""
        tree_with_c = {
            **TREE_V1,
            "activities": {
                **TREE_V1["activities"],
                "C": {
                    "id": "C",
                    "type": "ServiceActivity",
                    "optional": True,
                    "component": {"code": "t", "data": {}},
                },
            },
        }
        DebugContext.objects.create(template_id=3, space_id=10, tree_fingerprint=compute_tree_fingerprint(tree_with_c))
        # 当前 draft 删掉了 C
        svc = DebugService(template_id=3, space_id=10, pipeline_tree=TREE_V1)
        result = svc.reset_impact()
        assert set(result["reset_node_ids"]) == {"A", "B"}

    def test_topology_change_triggers_conservative_reset(self):
        """仅常量/连线整体指纹变化（无节点配置变更）→ 保守重置全部节点。"""
        DebugContext.objects.create(template_id=4, space_id=10, tree_fingerprint=compute_tree_fingerprint(TREE_V1))
        tree_v2 = {
            **TREE_V1,
            "constants": {
                "${g1}": {**TREE_V1["constants"]["${g1}"], "value": "CHANGED_DEFAULT"},
            },
        }
        svc = DebugService(template_id=4, space_id=10, pipeline_tree=tree_v2)
        result = svc.reset_impact()
        assert set(result["reset_node_ids"]) == {"A", "B"}

    def test_no_baseline_returns_empty_and_creates_nothing(self):
        """无历史 DebugContext（从未调试）→ 返回空且不写库（保持只读）。"""
        svc = DebugService(template_id=999, space_id=10, pipeline_tree=TREE_V1)
        result = svc.reset_impact()
        assert result["reset_node_ids"] == []
        assert result["reasons"] == {}
        assert DebugContext.objects.filter(template_id=999).count() == 0
