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
    return activity
