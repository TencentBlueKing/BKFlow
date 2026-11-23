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


def _get_template_names_map(template_ids, space_id):
    """按空间批量查询模板名称；不过滤软删模板，保证历史任务仍能展示流程名。"""
    from bkflow.template.models import Template

    return dict(Template.objects.filter(id__in=template_ids, space_id=space_id).values_list("id", "name"))


def enrich_task_list_result_template_names(result, space_id, names_map_getter=None):
    """按 template_id 批量补全任务列表的 template_name；旧 engine 无该字段或模板不存在时置空串。"""
    if not isinstance(result, dict) or not result.get("result"):
        return result
    results = (result.get("data") or {}).get("results")
    if not results:
        return result

    item_template_ids = []
    for item in results:
        try:
            item_template_ids.append(int(item.get("template_id")))
        except (TypeError, ValueError):
            item_template_ids.append(None)

    template_ids = {template_id for template_id in item_template_ids if template_id is not None}
    if names_map_getter is None:
        names_map_getter = _get_template_names_map
    template_names = names_map_getter(template_ids, space_id) if template_ids else {}

    for item, template_id in zip(results, item_template_ids):
        item["template_name"] = template_names.get(template_id, "")
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
