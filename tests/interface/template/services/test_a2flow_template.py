"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
    10|CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest.mock import Mock

import pytest

from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot

PIPELINE_TREE = {
    "activities": {"n1": {"id": "n1", "type": "ServiceActivity", "name": "重启"}},
    "gateways": {},
    "flows": {},
    "start_event": {"id": "start", "type": "EmptyStartEvent"},
    "end_event": {"id": "end", "type": "EmptyEndEvent"},
    "constants": {},
}
A2FLOW = {
    "version": "2.0",
    "name": "restart",
    "desc": "draft",
    "nodes": [{"id": "node_1", "name": "重启", "code": "demo_restart_service", "next": "end"}],
}


@pytest.fixture
def space(db):
    return Space.objects.create(name="a2flow-svc", app_code="bkflow_harness", platform_url="http://example.com")


@pytest.fixture
def convert_mocks(monkeypatch):
    convert = Mock(return_value=PIPELINE_TREE)
    monkeypatch.setattr(
        "bkflow.template.services.a2flow_template.A2FlowV2Converter.convert",
        convert,
    )
    monkeypatch.setattr("bkflow.template.services.a2flow_template.draw_pipeline", Mock())
    monkeypatch.setattr("bkflow.template.services.a2flow_template.replace_pipeline_tree_node_ids", Mock())
    return convert


@pytest.mark.django_db
def test_create_template_from_a2flow_sets_space_scope_and_app(space, convert_mocks):
    """创建模板写入空间、scope 和绑定应用。"""
    from bkflow.template.services.a2flow_template import create_template_from_a2flow

    template = create_template_from_a2flow(
        space_id=space.id,
        username="alice",
        a2flow=A2FLOW,
        scope_type="biz",
        scope_value="100",
        bind_app_code="bkflow_harness",
        auto_release=False,
    )
    assert isinstance(template, Template)
    assert template.space_id == space.id
    assert template.scope_type == "biz"
    assert template.scope_value == "100"
    assert template.bk_app_code == "bkflow_harness"
    assert template.name == "restart"


@pytest.mark.django_db
def test_update_template_draft_checks_space_and_app(space, convert_mocks):
    """更新草稿前必须核对空间和绑定应用。"""
    from bkflow.template.services.a2flow_template import (
        create_template_from_a2flow,
        update_template_draft_from_a2flow,
    )

    template = create_template_from_a2flow(
        space_id=space.id,
        username="alice",
        a2flow=A2FLOW,
        scope_type=None,
        scope_value=None,
        bind_app_code="bkflow_harness",
        auto_release=False,
    )
    snapshot = update_template_draft_from_a2flow(
        template=template,
        username="alice",
        a2flow={**A2FLOW, "desc": "updated"},
        expected_space_id=space.id,
        expected_bind_app_code="bkflow_harness",
    )
    assert isinstance(snapshot, TemplateSnapshot)
    with pytest.raises(PermissionError):
        update_template_draft_from_a2flow(
            template=template,
            username="alice",
            a2flow=A2FLOW,
            expected_space_id=space.id + 1,
            expected_bind_app_code="bkflow_harness",
        )
    with pytest.raises(PermissionError):
        update_template_draft_from_a2flow(
            template=template,
            username="alice",
            a2flow=A2FLOW,
            expected_space_id=space.id,
            expected_bind_app_code="other_app",
        )
