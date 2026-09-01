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
from typing import Optional

from django.db import transaction

from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
from bkflow.pipeline_web.drawing_new.drawing import draw_pipeline
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils.a2flow import A2FlowConverter
from bkflow.utils.canvas import OperateType
from bkflow.utils.pipeline import replace_pipeline_tree_node_ids


def _build_pipeline_tree(a2flow, space_id, username, scope_type, scope_value, *, remap_ids=True):
    if isinstance(a2flow, dict):
        pipeline_tree = A2FlowV2Converter(
            a2flow,
            space_id=int(space_id),
            username=username,
            scope_type=scope_type,
            scope_value=scope_value,
        ).convert()
    else:
        pipeline_tree = A2FlowConverter(a2flow).convert()
    try:
        draw_pipeline(pipeline_tree)
    except Exception as exc:
        raise RuntimeError("流程自动排版失败: {}".format(exc)) from exc
    if remap_ids:
        replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)
    return pipeline_tree


def _create_snapshot(space_id, pipeline_tree, username, auto_release):
    if SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true":
        if auto_release:
            return TemplateSnapshot.create_draft_snapshot(pipeline_tree, username, "1.0.0")
        return TemplateSnapshot.create_draft_snapshot(pipeline_tree, username)
    return TemplateSnapshot.create_snapshot(pipeline_tree, username, "1.0.0")


def create_template_from_a2flow(
    *,
    space_id: int,
    username: str,
    a2flow: dict,
    scope_type: Optional[str],
    scope_value: Optional[str],
    bind_app_code: str,
    auto_release: bool = False,
    name: Optional[str] = None,
    desc: str = "",
) -> Template:
    """从 a2flow 创建模板，保留现有 auto_release / 版本管理策略。"""
    display_name = name
    display_desc = desc
    if isinstance(a2flow, dict):
        display_name = display_name or a2flow.get("name", "")
        display_desc = display_desc or a2flow.get("desc", "")
    pipeline_tree = _build_pipeline_tree(a2flow, space_id, username, scope_type, scope_value)
    with transaction.atomic():
        template_data = {
            "name": display_name,
            "desc": display_desc,
            "space_id": space_id,
            "creator": username,
            "updated_by": username,
            "bk_app_code": bind_app_code or None,
        }
        if scope_type:
            template_data["scope_type"] = scope_type
            template_data["scope_value"] = scope_value
        snapshot = _create_snapshot(space_id, pipeline_tree, username, auto_release)
        template = Template.objects.create(**template_data, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
    return template


def update_template_draft_from_a2flow(
    *,
    template: Template,
    username: str,
    a2flow: dict,
    expected_space_id: int,
    expected_bind_app_code: str,
) -> TemplateSnapshot:
    """在核对空间和绑定应用后，原位更新模板草稿。"""
    if template.space_id != expected_space_id:
        raise PermissionError("template space does not match the trusted space")
    if (template.bk_app_code or "") != (expected_bind_app_code or ""):
        raise PermissionError("template app binding does not match the trusted app")
    pipeline_tree = _build_pipeline_tree(
        a2flow,
        template.space_id,
        username,
        template.scope_type,
        template.scope_value,
        remap_ids=False,
    )
    return template.update_draft_snapshot(pipeline_tree, username)
