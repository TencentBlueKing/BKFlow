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

import logging
import re

logger = logging.getLogger("root")

_MISSING_ROUTE_STATUS = re.compile(r"status_code:\s*(404|405)\b")
# SimpleGenericViewSet 会把 DRF NotFound 改写成 HTTP 200 + code=not_found
_DEFAULT_NOT_FOUND_MESSAGES = {"未找到。", "Not found."}


def is_engine_route_missing(result):
    """判断 engine 调用失败是否因为目标路由不存在（未升级的旧 engine）。"""
    if not isinstance(result, dict) or result.get("result") is not False:
        return False
    message = str(result.get("message") or "")
    if _MISSING_ROUTE_STATUS.search(message):
        return True
    detail = ""
    data = result.get("data")
    if isinstance(data, dict):
        detail = str(data.get("detail") or "")
    return result.get("code") == "not_found" and (
        message in _DEFAULT_NOT_FOUND_MESSAGES or detail in _DEFAULT_NOT_FOUND_MESSAGES
    )


def empty_wrapped_result(data):
    """构造与已升级 engine（SimpleGenericViewSet 包装）一致的成功结构。"""
    return {"result": True, "data": data, "code": "0", "message": ""}


def fallback_if_engine_route_missing(result, fallback):
    """旧 engine 缺路由时返回 fallback，其它响应原样透传。"""
    if is_engine_route_missing(result):
        logger.warning("engine route missing, fallback to compatible empty payload: %s", result.get("message"))
        return fallback
    return result


def enrich_task_list_result_labels(result, labels_map_getter=None):
    """将任务列表中的 label id 转成标签对象；旧 engine 无 labels 字段时视为空。"""
    if not isinstance(result, dict) or not result.get("result"):
        return result
    results = (result.get("data") or {}).get("results")
    if not results:
        return result

    label_ids = []
    for item in results:
        label_ids.extend(item.get("labels") or [])

    if labels_map_getter is None:
        from bkflow.label.models import Label

        labels_map_getter = Label.objects.get_labels_map
    labels_map = labels_map_getter(set(label_ids)) if label_ids else {}

    for item in results:
        item["labels"] = [labels_map.get(label_id) for label_id in (item.get("labels") or [])]
    return result


def parse_task_ids(task_ids_param):
    """解析逗号分隔的任务 ID，忽略空值和非法值。"""
    if not task_ids_param:
        return []
    parsed = []
    for raw in str(task_ids_param).split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed.append(int(raw))
        except (TypeError, ValueError):
            continue
    return parsed
