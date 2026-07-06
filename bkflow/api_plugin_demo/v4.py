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

import copy

from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response

WRAPPER_VERSION = "v4.0.0"
DEMO_CATEGORIES = [{"name": "V4 协议验证", "id": "v4"}]


DEMO_PLUGINS = {
    "demo_polling_job": {
        "id": "demo_polling_job",
        "name": "V4 Polling Demo 作业",
        "category": "v4",
        "plugin_source": "demo",
        "plugin_code": "demo_polling_job",
        "description": "用于 stage 环境验证 uniform_api v4.0.0 polling 调度协议",
        "default_version": "1.0.0",
        "latest_version": "1.1.0",
        "versions": ["1.0.0", "1.1.0"],
        "schedule_mode": "polling",
        "inputs": [
            {
                "key": "target_ip",
                "name": "目标 IP",
                "desc": "用于验证 inputs 透传的目标 IP",
                "required": True,
                "type": "string",
                "form_type": "input",
            },
            {
                "key": "sleep_seconds",
                "name": "模拟耗时",
                "desc": "仅用于 stage 联调展示，不影响实际等待",
                "required": False,
                "type": "int",
                "default": 1,
            },
        ],
        "outputs": [
            {
                "key": "job_instance_id",
                "name": "作业实例 ID",
                "desc": "demo 生成的作业实例标识",
                "type": "string",
            },
            {
                "key": "message",
                "name": "执行结果",
                "desc": "demo 执行结果说明",
                "type": "string",
            },
        ],
    },
    "demo_callback_job": {
        "id": "demo_callback_job",
        "name": "V4 Callback Demo 作业",
        "category": "v4",
        "plugin_source": "demo",
        "plugin_code": "demo_callback_job",
        "description": "用于 stage 环境验证 uniform_api v4.0.0 callback 调度协议",
        "default_version": "2.0.0",
        "latest_version": "2.0.0",
        "versions": ["2.0.0"],
        "schedule_mode": "callback",
        "inputs": [
            {
                "key": "message",
                "name": "回调消息",
                "desc": "用于验证 callback 分支的自定义消息",
                "required": False,
                "type": "string",
                "form_type": "input",
            }
        ],
        "outputs": [
            {
                "key": "job_instance_id",
                "name": "作业实例 ID",
                "desc": "demo 生成的作业实例标识",
                "type": "string",
            },
            {
                "key": "message",
                "name": "回调结果",
                "desc": "demo 回调结果说明",
                "type": "string",
            },
        ],
    },
}


def _demo_response(result=True, data=None, message=""):
    """构建 demo API 标准三段响应。"""
    return Response({"result": result, "message": message, "data": data if data is not None else {}})


def _build_api_url(request, path):
    """构建对外 API URL，优先使用网关地址模板。"""
    try:
        if hasattr(settings, "BK_API_URL_TMPL") and hasattr(settings, "BK_APIGW_NAME"):
            return "{}{}".format(settings.BK_API_URL_TMPL.format(api_name=settings.BK_APIGW_NAME), path)
    except Exception:
        pass

    if request:
        return request.build_absolute_uri(path)
    return path


def _get_api_plugin_demo_stage():
    """获取 APIGW 对外暴露的环境路径。"""
    return getattr(settings, "BK_APIGW_STAGE_NAME", "") or getattr(settings, "ENVIRONMENT", "") or "stage"


def _build_api_plugin_demo_path(path):
    """构建 api_plugin_demo v4 对外访问路径。"""
    return "/{}/api_plugin_demo/v4/{}".format(_get_api_plugin_demo_stage(), path.lstrip("/"))


def _get_plugin_config(plugin_id):
    """获取 v4 demo 插件配置。"""
    config = DEMO_PLUGINS.get(plugin_id)
    return copy.deepcopy(config) if config else None


def _list_plugins(limit, offset, category, request=None):
    """获取 v4 demo 插件列表。"""
    plugins = list(DEMO_PLUGINS.values())
    if category:
        plugins = [plugin for plugin in plugins if plugin["category"] == category]

    items = []
    for plugin in plugins[offset : offset + limit]:
        detail_path = _build_api_plugin_demo_path("detail_meta/?api_id={}&version={{version}}".format(plugin["id"]))
        items.append(
            {
                "id": plugin["id"],
                "name": plugin["name"],
                "plugin_source": plugin["plugin_source"],
                "plugin_code": plugin["plugin_code"],
                "wrapper_version": WRAPPER_VERSION,
                "default_version": plugin["default_version"],
                "latest_version": plugin["latest_version"],
                "versions": copy.deepcopy(plugin["versions"]),
                "meta_url_template": _build_api_url(request, detail_path),
                "category": plugin["category"],
                "description": plugin["description"],
            }
        )
    return {"total": len(plugins), "apis": items}


def _get_plugin_detail(plugin_id, version=None, request=None):
    """获取 v4 demo 插件指定业务版本详情。"""
    plugin = _get_plugin_config(plugin_id)
    if not plugin:
        return None

    plugin_version = version or plugin["default_version"]
    if plugin_version not in plugin["versions"]:
        raise ValueError("open plugin demo [{}] version [{}] not found".format(plugin_id, plugin_version))

    detail = {
        "id": plugin["id"],
        "name": plugin["name"],
        "desc": plugin["description"],
        "description": plugin["description"],
        "plugin_source": plugin["plugin_source"],
        "plugin_code": plugin["plugin_code"],
        "plugin_version": plugin_version,
        "wrapper_version": WRAPPER_VERSION,
        "url": _build_api_url(request, _build_api_plugin_demo_path("execute/")),
        "methods": ["POST"],
        "inputs": copy.deepcopy(plugin["inputs"]),
        "outputs": copy.deepcopy(plugin["outputs"]),
    }

    if plugin["schedule_mode"] == "polling":
        detail["polling"] = {
            "url": _build_api_url(request, _build_api_plugin_demo_path("status/")),
            "task_tag_key": "open_plugin_run_id",
            "success_tag": {"key": "status", "value": "SUCCEEDED", "data_key": "outputs"},
            "fail_tag": {"key": "status", "value": "FAILED", "msg_key": "error_message"},
            "running_tag": {"key": "status", "value": "RUNNING"},
        }
    elif plugin["schedule_mode"] == "callback":
        detail["callback"] = {"enabled": True}

    return detail


def _build_outputs(open_plugin_run_id):
    """按 run id 生成稳定的 demo outputs。"""
    run_token = open_plugin_run_id.split(":", 1)[-1]
    return {
        "job_instance_id": "demo-job-{}".format(run_token),
        "message": "demo open plugin finished",
    }


@api_view(["GET"])
def category_api(request):
    """获取 v4 协议验证插件分类。"""
    return _demo_response(data=copy.deepcopy(DEMO_CATEGORIES))


@api_view(["GET"])
def list_meta_api(request):
    """获取 v4 协议验证插件目录。"""
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    category = request.query_params.get("category", "")

    return _demo_response(data=_list_plugins(limit=limit, offset=offset, category=category, request=request))


@api_view(["GET"])
def detail_meta_api(request):
    """获取 v4 协议验证插件详情。"""
    plugin_id = request.query_params.get("api_id", "")
    version = request.query_params.get("version", "")
    if not plugin_id:
        return _demo_response(result=False, message="api_id parameter is required")

    try:
        detail = _get_plugin_detail(plugin_id, version=version or None, request=request)
    except ValueError as e:
        return _demo_response(result=False, message=str(e))

    if not detail:
        return _demo_response(result=False, message="API {} not found".format(plugin_id))
    return _demo_response(data=detail)


@api_view(["POST"])
def execute_api(request):
    """模拟 v4 execute 响应。"""
    plugin_id = request.data.get("plugin_id", "")
    plugin_version = request.data.get("plugin_version", "")
    client_request_id = request.data.get("client_request_id", "")
    inputs = request.data.get("inputs", {})
    context = request.data.get("context", {})

    if not plugin_id:
        return _demo_response(result=False, message="plugin_id parameter is required")
    if not client_request_id:
        return _demo_response(result=False, message="client_request_id parameter is required")

    try:
        _get_plugin_detail(plugin_id, version=plugin_version or None, request=request)
    except ValueError as e:
        return _demo_response(result=False, message=str(e))

    plugin = _get_plugin_config(plugin_id)
    if not plugin:
        return _demo_response(result=False, message="API {} not found".format(plugin_id))

    open_plugin_run_id = "{}:{}".format(plugin_id, client_request_id)
    status = "WAITING_CALLBACK" if plugin["schedule_mode"] == "callback" else "RUNNING"
    return _demo_response(
        data={
            "open_plugin_run_id": open_plugin_run_id,
            "status": status,
            "received_inputs": inputs,
            "received_context": context,
            "callback_url_received": bool(request.data.get("callback_url")),
            "callback_token_received": bool(request.data.get("callback_token")),
        }
    )


@api_view(["GET"])
def status_api(request):
    """模拟 v4 polling 状态查询。"""
    open_plugin_run_id = request.query_params.get("task_tag") or request.query_params.get("open_plugin_run_id", "")
    status = request.query_params.get("status", "SUCCEEDED")
    if not open_plugin_run_id:
        return _demo_response(result=False, message="task_tag parameter is required")

    data = {"open_plugin_run_id": open_plugin_run_id, "status": status}
    if status == "SUCCEEDED":
        data["outputs"] = _build_outputs(open_plugin_run_id)
    elif status == "FAILED":
        data["error_message"] = "demo open plugin failed"

    return _demo_response(data=data)


@api_view(["GET", "POST"])
def cancel_api(request, open_plugin_run_id):
    """模拟取消 v4 开放插件运行实例。"""
    return _demo_response(data={"open_plugin_run_id": open_plugin_run_id, "status": "CANCELLED"})
