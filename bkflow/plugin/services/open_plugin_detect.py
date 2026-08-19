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

from copy import deepcopy

REFERENCE_SNAPSHOT_KEY = "plugin_reference_snapshot"
OPEN_PLUGIN_WRAPPER_VERSION = "v4.0.0"


def extract_data_value(data, key):
    """读取 pipeline 节点 data 字段中的值。"""
    value = (data or {}).get(key)
    if isinstance(value, dict):
        return value.get("value")
    return value


def is_open_plugin_component(component):
    """判断 uniform_api 节点是否使用开放插件 v4 协议。不访问数据库。"""
    data = (component or {}).get("data", {})
    api_meta = (component or {}).get("api_meta", {})
    if extract_data_value(data, "uniform_api_plugin_id"):
        return True

    wrapper_version = api_meta.get("wrapper_version") or (component or {}).get("version")
    if wrapper_version == OPEN_PLUGIN_WRAPPER_VERSION:
        return True

    # 兼容早期页面曾将业务版本写入 component.version 的开放插件节点。
    return bool(api_meta.get("versions") and api_meta.get("meta_url_template"))


def has_open_plugin_nodes(pipeline_tree):
    """仅根据 pipeline 结构判断是否包含开放插件节点。"""
    activities = (pipeline_tree or {}).get("activities", {})
    if not isinstance(activities, dict):
        return False
    for node in activities.values():
        if not isinstance(node, dict) or node.get("type") != "ServiceActivity":
            continue
        component = node.get("component") or {}
        if component.get("code") != "uniform_api":
            continue
        if is_open_plugin_component(component):
            return True
    return False


def get_reference_snapshot(extra_info):
    """读取任务 extra_info 中的开放插件引用快照。"""
    return deepcopy((extra_info or {}).get(REFERENCE_SNAPSHOT_KEY) or [])


def needs_start_validation(extra_info=None, pipeline_tree=None):
    """启动时是否需要做开放插件准入预检。"""
    if get_reference_snapshot(extra_info):
        return True
    return has_open_plugin_nodes(pipeline_tree)
