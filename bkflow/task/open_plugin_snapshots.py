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

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.exceptions import ValidationError
from bkflow.plugin.services.open_plugin_detect import (
    REFERENCE_SNAPSHOT_KEY,
    has_open_plugin_nodes,
)

SCHEMA_SNAPSHOT_KEY = "plugin_schema_snapshot"


def build_engine_snapshot_request(
    space_id,
    pipeline_tree,
    extra_info=None,
    username=None,
    scope_type=None,
    scope_id=None,
    mode="prepare",
):
    """构造 Engine 调用 Interface 快照接口的请求体，只传快照字段。"""
    extra = extra_info or {}
    return {
        "space_id": space_id,
        "pipeline_tree": pipeline_tree,
        "username": username,
        "scope_type": scope_type,
        "scope_value": scope_id,
        "mode": mode,
        "plugin_reference_snapshot": extra.get(REFERENCE_SNAPSHOT_KEY) or [],
        "plugin_schema_snapshot": extra.get(SCHEMA_SNAPSHOT_KEY) or {},
    }


def merge_snapshot_response(extra_info, data):
    """把 Interface 返回的快照合并进本地 extra_info，不覆盖其它字段。"""
    extra = dict(extra_info or {})
    extra[REFERENCE_SNAPSHOT_KEY] = data.get("reference_snapshot") or []
    extra[SCHEMA_SNAPSHOT_KEY] = data.get("schema_snapshot") or {}
    return extra


def prepare_engine_task_extra_info(
    space_id,
    pipeline_tree,
    extra_info=None,
    username=None,
    scope_type=None,
    scope_id=None,
):
    """Engine 创建任务前写入开放插件快照。普通任务不请求 Interface。"""
    extra = dict(extra_info or {})
    if not has_open_plugin_nodes(pipeline_tree):
        return extra

    result = InterfaceModuleClient().build_open_plugin_snapshots(
        build_engine_snapshot_request(
            space_id=space_id,
            pipeline_tree=pipeline_tree,
            extra_info=extra,
            username=username,
            scope_type=scope_type,
            scope_id=scope_id,
            mode="prepare",
        )
    )
    if not result or not result.get("result"):
        raise ValidationError((result or {}).get("message") or "开放插件快照构建失败")

    return merge_snapshot_response(extra, result.get("data") or {})


def has_complete_open_plugin_snapshots(extra_info):
    """任务 extra_info 是否已同时包含引用快照和 schema 快照。"""
    extra = extra_info or {}
    return bool(extra.get(REFERENCE_SNAPSHOT_KEY)) and bool(extra.get(SCHEMA_SNAPSHOT_KEY))
