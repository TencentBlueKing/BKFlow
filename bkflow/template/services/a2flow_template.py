"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

Template creation from server-owned a2flow documents.
"""
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter
from bkflow.pipeline_web.drawing_new.drawing import draw_pipeline
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils.canvas import OperateType
from bkflow.utils.pipeline import replace_pipeline_tree_node_ids


def _pipeline_tree(a2flow, space_id, username, scope_type, scope_value):
    if not isinstance(a2flow, dict):
        raise ValidationError("a2flow must be an object")
    tree = A2FlowV2Converter(
        a2flow, space_id=space_id, username=username, scope_type=scope_type, scope_value=scope_value
    ).convert()
    draw_pipeline(tree)
    replace_pipeline_tree_node_ids(tree, OperateType.CREATE_TEMPLATE.value)
    return tree


def create_template_from_a2flow(
    *,
    space_id: int,
    username: str,
    a2flow: dict,
    scope_type: Optional[str],
    scope_value: Optional[str],
    bind_app_code: str,
    auto_release: bool = False,
) -> Template:
    """Create one template and its initial snapshot from an authoritative a2flow document."""
    tree = _pipeline_tree(a2flow, space_id, username, scope_type, scope_value)
    with transaction.atomic():
        versioning = SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true"
        snapshot = (
            TemplateSnapshot.create_draft_snapshot(tree, username, "1.0.0")
            if versioning and auto_release
            else (
                TemplateSnapshot.create_draft_snapshot(tree, username)
                if versioning
                else TemplateSnapshot.create_snapshot(tree, username, "1.0.0")
            )
        )
        template = Template.objects.create(
            name=a2flow.get("name", ""),
            desc=a2flow.get("desc", ""),
            space_id=space_id,
            scope_type=scope_type,
            scope_value=scope_value,
            bk_app_code=bind_app_code,
            creator=username,
            updated_by=username,
            snapshot_id=snapshot.id,
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template


def create_template_draft_from_pipeline_tree(
    *, pipeline_tree, name, desc, space_id, username, scope_type, scope_value, bind_app_code
):
    """Persist a pre-converted, governed tree as a draft in every space configuration."""
    with transaction.atomic():
        snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username)
        template = Template.objects.create(
            name=name,
            desc=desc,
            space_id=space_id,
            scope_type=scope_type,
            scope_value=scope_value,
            bk_app_code=bind_app_code,
            creator=username,
            updated_by=username,
            snapshot_id=snapshot.id,
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template


def update_template_draft_from_a2flow(
    *, template: Template, username: str, a2flow: dict, expected_space_id: int, expected_bind_app_code: str
) -> TemplateSnapshot:
    """Update only the owned managed template's draft snapshot."""
    if template.space_id != expected_space_id or template.bk_app_code != expected_bind_app_code:
        raise ValidationError("template ownership does not match the trusted Harness context")
    tree = _pipeline_tree(a2flow, expected_space_id, username, template.scope_type, template.scope_value)
    return template.update_draft_snapshot(tree, username)


def update_template_draft_from_pipeline_tree(
    *, template, username, pipeline_tree, expected_space_id, expected_bind_app_code
):
    """Update the owned managed draft with the already-governed pipeline tree."""
    if template.space_id != expected_space_id or template.bk_app_code != expected_bind_app_code:
        raise ValidationError("template ownership does not match the trusted Harness context")
    return template.update_draft_snapshot(pipeline_tree, username)
