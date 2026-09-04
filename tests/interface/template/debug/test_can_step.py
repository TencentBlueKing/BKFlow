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

from bkflow.template.debug.service import DebugService

TREE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "B": {
            "id": "B",
            "type": "ServiceActivity",
            "component": {"code": "t", "data": {"y": {"hook": True, "value": "${g1}"}}},
        },
    },
    "flows": {},
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

SUBCANVAS_TREE = {
    "activities": {
        "A": {"id": "A", "type": "ServiceActivity", "component": {"code": "t", "data": {}}},
        "S": {
            "id": "S",
            "type": "SubCanvas",
            "loop_config": {
                "enable": True,
                "type": "array_loop",
                "loop_times": None,
                "loop_params": {"${loop_item}": "${g1}"},
            },
            "pipeline": {
                "activities": {},
                "flows": {},
                "gateways": {},
                "constants": {
                    "${inner_input}": {
                        "key": "${inner_input}",
                        "show_type": "show",
                        "need_render": True,
                        "value": {"items": ["${g1}"]},
                    }
                },
            },
        },
    },
    "flows": {},
    "gateways": {},
    "constants": TREE["constants"],
}


@pytest.mark.django_db
class TestCanStep:
    def test_no_dependency_node_can_step(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        can, missing = svc.compute_can_step(ctx, "A")
        assert can is True and missing == []

    def test_consumer_blocked_until_producer_ran(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=TREE)
        ctx = svc.get_or_create_context()
        can, missing = svc.compute_can_step(ctx, "B")
        assert can is False
        assert missing == [{"key": "${g1}", "source_node_id": "A"}]
        ctx.global_vars = {"${g1}": "v"}
        ctx.save()
        can2, missing2 = svc.compute_can_step(ctx, "B")
        assert can2 is True and missing2 == []

    def test_subcanvas_blocked_until_loop_and_inner_dependencies_exist(self):
        svc = DebugService(template_id=1, space_id=10, pipeline_tree=SUBCANVAS_TREE)
        ctx = svc.get_or_create_context()

        can, missing = svc.compute_can_step(ctx, "S")

        assert can is False
        assert missing == [{"key": "${g1}", "source_node_id": "A"}]

        ctx.global_vars = {"${g1}": ["first", "second"]}
        ctx.save(update_fields=["global_vars"])

        assert svc.compute_can_step(ctx, "S") == (True, [])
