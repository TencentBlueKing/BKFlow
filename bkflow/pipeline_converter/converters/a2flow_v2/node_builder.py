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
from typing import Any, Dict, List, Optional, Union

from bkflow.pipeline_converter.constants import (
    DEFAULT_ACTIVITY_CONFIG,
    A2FlowPluginType,
)
from bkflow.pipeline_converter.converters.a2flow_v2.plugin_resolver import (
    ResolvedPlugin,
)
from bkflow.pipeline_web.preview import preview_template_tree
from bkflow.template.models import Template


def build_start_event(node_id, name, outgoing):
    return {"id": node_id, "name": name, "type": "EmptyStartEvent", "incoming": "", "outgoing": outgoing, "labels": []}


def build_end_event(node_id, name, incoming):
    return {"id": node_id, "name": name, "type": "EmptyEndEvent", "incoming": incoming, "outgoing": "", "labels": []}


def _wrap_data_value(value):
    if isinstance(value, dict) and "hook" in value and "value" in value:
        return value
    return {"hook": False, "need_render": True, "value": value}


def _build_component_data(data, plugin):
    normalized = {k: _wrap_data_value(v) for k, v in data.items()}
    if plugin.plugin_type == A2FlowPluginType.REMOTE_PLUGIN.value:
        normalized["plugin_code"] = _wrap_data_value(plugin.original_code)
        normalized["plugin_version"] = _wrap_data_value(plugin.remote_plugin_version or "")
    elif plugin.plugin_type == A2FlowPluginType.UNIFORM_API.value and plugin.api_meta:
        normalized["uniform_api_plugin_url"] = _wrap_data_value(plugin.api_meta["url"])
        normalized["uniform_api_plugin_method"] = _wrap_data_value(plugin.api_meta["methods"][0])
        if plugin.api_meta.get("api_key"):
            normalized["uniform_api_plugin_credential_key"] = _wrap_data_value(plugin.api_meta["api_key"])
    return normalized


def build_activity(
    node_id: str,
    name: str,
    data: Dict[str, Any],
    plugin: ResolvedPlugin,
    incoming: Union[str, List[str]],
    outgoing: Union[str, List[str]],
    stage_name: Optional[str] = None,
    failure_strategy=None,
) -> dict:
    component_data = _build_component_data(data, plugin)
    activity = {
        "id": node_id,
        "name": name,
        "type": "ServiceActivity",
        "incoming": incoming,
        "outgoing": outgoing,
        "stage_name": stage_name or name,
        "component": {"code": plugin.wrapper_code, "version": plugin.wrapper_version, "data": component_data},
    }
    if plugin.plugin_type == A2FlowPluginType.UNIFORM_API.value and plugin.api_meta:
        activity["component"]["api_meta"] = plugin.api_meta
    activity.update(DEFAULT_ACTIVITY_CONFIG)
    if failure_strategy is not None:
        fs = failure_strategy.dict(exclude_none=True)
        activity.update(fs)
    return activity


def build_subprocess(
    node_id: str,
    name: str,
    template_id: Any,
    incoming: Union[str, List[str]],
    outgoing: Union[str, List[str]],
    stage_name: Optional[str] = None,
    always_use_latest: bool = False,
    constants: Optional[Dict[str, Any]] = None,
    failure_strategy=None,
) -> dict:
    """
    构建 SubProcess 类型的 activity 节点（最小字段版本）。
    """
    template = Template.objects.get(id=template_id)
    data = preview_template_tree(template.pipeline_tree, None)
    sub_constants = data["pipeline_tree"]["constants"]
    override_constants = constants or {}
    for key, info in sub_constants.items():
        if key in override_constants:
            info["value"] = override_constants[key]

    subprocess_node = {
        "id": node_id,
        "name": name,
        "type": "SubProcess",
        "incoming": incoming,
        "outgoing": outgoing,
        "stage_name": stage_name or name,
        "template_id": template_id,
        "version": template.version,
        "always_use_latest": always_use_latest,
        "constants": sub_constants,
    }
    subprocess_node.update(DEFAULT_ACTIVITY_CONFIG)
    if failure_strategy is not None:
        fs = failure_strategy.dict(exclude_none=True)
        subprocess_node.update(fs)
    return subprocess_node
