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

from rest_framework.decorators import api_view
from rest_framework.response import Response

from bkflow.api_plugin_demo.plugins import (
    get_api_detail,
    get_api_list,
    get_category_list,
    get_open_plugin_v4_api_config,
    get_open_plugin_v4_api_detail,
    get_open_plugin_v4_api_list,
)


def _demo_response(result=True, data=None, message=""):
    """构建 demo API 标准三段响应。"""
    return Response(
        {
            "result": result,
            "message": message,
            "data": data if data is not None else {},
        }
    )


def _open_plugin_v4_outputs(open_plugin_run_id):
    """按 run id 生成稳定的 demo outputs。"""
    run_token = open_plugin_run_id.split(":", 1)[-1]
    return {
        "job_instance_id": "demo-job-{}".format(run_token),
        "message": "demo open plugin finished",
    }


@api_view(["GET"])
def category_api(request):
    """
    Category API - 获取接口分类信息
    输入: GET方法，形如 category_api/?scope_value=xx&scope_type=xx
    输出: 标准三段结构，result为True时展示接口列表
    """
    scope_value = request.query_params.get("scope_value", "")
    scope_type = request.query_params.get("scope_type", "")

    try:
        categories = get_category_list(scope_type, scope_value)
        return Response(
            {
                "result": True,
                "message": "",
                "data": categories,
            }
        )
    except Exception as e:
        return Response(
            {
                "result": False,
                "message": str(e),
                "data": [],
            }
        )


@api_view(["GET"])
def list_meta_api(request):
    """
    List Meta API - 获取接口列表数据
    输入: GET方法，分页参数采用limit + offset的协议
    形如: list_meta_api/?limit=50&offset=0&scope_type=xx&scope_value=xxx&category=xxx
    输出: 标准三段结构，result为True时展示接口列表
    """
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    scope_type = request.query_params.get("scope_type", "")
    scope_value = request.query_params.get("scope_value", "")
    category = request.query_params.get("category", "")

    try:
        api_list_data = get_api_list(limit, offset, scope_type, scope_value, category, request)
        return Response(
            {
                "result": True,
                "message": "",
                "data": api_list_data,
            }
        )
    except Exception as e:
        return Response(
            {
                "result": False,
                "message": str(e),
                "data": {"total": 0, "apis": []},
            }
        )


@api_view(["GET"])
def detail_meta_api(request):
    """
    Detail Meta API - 获取接口详情的元数据
    输入: GET方法，需要传入api_id参数
    输出: 标准三段结构，result为True时展示接口详情
    """
    api_id = request.query_params.get("api_id", "")

    if not api_id:
        return Response(
            {
                "result": False,
                "message": "api_id parameter is required",
                "data": {},
            }
        )

    try:
        api_detail = get_api_detail(api_id, request)
        if api_detail:
            return Response(
                {
                    "result": True,
                    "message": "",
                    "data": api_detail,
                }
            )
        else:
            return Response(
                {
                    "result": False,
                    "message": f"API {api_id} not found",
                    "data": {},
                }
            )
    except Exception as e:
        return Response(
            {
                "result": False,
                "message": str(e),
                "data": {},
            }
        )


@api_view(["GET"])
def execute_get_user_info(request):
    """
    执行API插件1: 获取用户信息
    这是一个简单的GET请求示例
    """
    username = request.query_params.get("username", "")
    include_details = request.query_params.get("include_details", "false").lower() == "true"

    if not username:
        return Response(
            {
                "result": False,
                "message": "username parameter is required",
                "data": {},
            }
        )

    # 模拟返回用户信息
    user_data = {
        "user_id": f"user_{username}_001",
        "username": username,
        "email": f"{username}@example.com",
    }

    if include_details:
        user_data.update(
            {
                "phone": "13800138000",
                "department": "技术部",
                "role": "developer",
            }
        )

    return Response(
        {
            "result": True,
            "message": "",
            "data": user_data,
        }
    )


@api_view(["POST"])
def execute_create_task(request):
    """
    执行API插件2: 创建任务
    这是一个简单的POST请求示例
    """
    task_name = request.data.get("task_name", "")
    description = request.data.get("description", "")
    priority = request.data.get("priority", "medium")
    tags = request.data.get("tags", [])

    if not task_name:
        return Response(
            {
                "result": False,
                "message": "task_name parameter is required",
                "data": {},
            }
        )

    # 模拟创建任务
    import uuid

    task_id = str(uuid.uuid4())[:8]

    task_data = {
        "task_id": task_id,
        "task_name": task_name,
        "status": "created",
        "priority": priority,
        "description": description,
        "tags": tags if isinstance(tags, list) else [],
    }

    return Response(
        {
            "result": True,
            "message": "Task created successfully",
            "data": task_data,
        }
    )


@api_view(["POST"])
def execute_process_data(request):
    """
    执行API插件3: 处理数据
    这是一个POST请求示例，包含表格数据处理
    """
    operation = request.data.get("operation", "")
    data_items = request.data.get("data_items", [])

    if not operation:
        return Response(
            {
                "result": False,
                "message": "operation parameter is required",
                "data": {},
            }
        )

    if not data_items or not isinstance(data_items, list):
        return Response(
            {
                "result": False,
                "message": "data_items parameter is required and must be a list",
                "data": {},
            }
        )

    # 提取所有数值
    values = []
    for item in data_items:
        if isinstance(item, dict) and "value" in item:
            try:
                values.append(int(item["value"]))
            except (ValueError, TypeError):
                continue

    if not values:
        return Response(
            {
                "result": False,
                "message": "No valid numeric values found in data_items",
                "data": {},
            }
        )

    # 根据操作类型计算结果
    result_value = None
    if operation == "sum":
        result_value = sum(values)
    elif operation == "avg":
        result_value = sum(values) / len(values) if values else 0
    elif operation == "max":
        result_value = max(values)
    elif operation == "min":
        result_value = min(values)
    else:
        return Response(
            {
                "result": False,
                "message": f"Unsupported operation: {operation}",
                "data": {},
            }
        )

    return Response(
        {
            "result": True,
            "message": "",
            "data": {
                "result": str(result_value),
                "processed_count": len(values),
                "operation": operation,
            },
        }
    )


@api_view(["POST"])
def execute_api_with_credential(request):
    """
    执行API插件4: 使用自定义凭证的API
    这是一个演示credential_key功能的示例
    """
    resource_id = request.data.get("resource_id", "")
    action = request.data.get("action", "create")

    if not resource_id:
        return Response(
            {
                "result": False,
                "message": "resource_id parameter is required",
                "data": {},
            }
        )

    # 模拟操作结果
    status_map = {
        "create": "created",
        "update": "updated",
        "delete": "deleted",
    }

    message_map = {
        "create": "资源创建成功",
        "update": "资源更新成功",
        "delete": "资源删除成功",
    }

    return Response(
        {
            "result": True,
            "message": "",
            "data": {
                "resource_id": resource_id,
                "action": action,
                "status": status_map.get(action, "unknown"),
                "message": message_map.get(action, "操作完成"),
            },
        }
    )


@api_view(["GET"])
def open_plugin_v4_list_meta_api(request):
    """
    Open Plugin V4 List Meta API - 获取 stage 联调用开放插件目录。
    """
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    scope_type = request.query_params.get("scope_type", "")
    scope_value = request.query_params.get("scope_value", "")
    category = request.query_params.get("category", "")

    api_list_data = get_open_plugin_v4_api_list(limit, offset, scope_type, scope_value, category, request)
    return _demo_response(data=api_list_data)


@api_view(["GET"])
def open_plugin_v4_detail_meta_api(request):
    """
    Open Plugin V4 Detail Meta API - 获取指定业务版本 schema。
    """
    api_id = request.query_params.get("api_id", "")
    version = request.query_params.get("version", "")
    if not api_id:
        return _demo_response(result=False, message="api_id parameter is required")

    try:
        api_detail = get_open_plugin_v4_api_detail(api_id, version=version or None, request=request)
    except ValueError as e:
        return _demo_response(result=False, message=str(e))

    if not api_detail:
        return _demo_response(result=False, message="API {} not found".format(api_id))
    return _demo_response(data=api_detail)


@api_view(["POST"])
def open_plugin_v4_execute_api(request):
    """
    Open Plugin V4 Execute API - 模拟 SOPS open plugin execute 响应。
    """
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
        get_open_plugin_v4_api_detail(plugin_id, version=plugin_version or None, request=request)
    except ValueError as e:
        return _demo_response(result=False, message=str(e))

    api_config = get_open_plugin_v4_api_config(plugin_id)
    if not api_config:
        return _demo_response(result=False, message="API {} not found".format(plugin_id))

    open_plugin_run_id = "{}:{}".format(plugin_id, client_request_id)
    status = "WAITING_CALLBACK" if api_config["schedule_mode"] == "callback" else "RUNNING"
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
def open_plugin_v4_status_api(request):
    """
    Open Plugin V4 Status API - 模拟 polling 状态查询。
    """
    open_plugin_run_id = request.query_params.get("task_tag") or request.query_params.get("open_plugin_run_id", "")
    status = request.query_params.get("status", "SUCCEEDED")
    if not open_plugin_run_id:
        return _demo_response(result=False, message="task_tag parameter is required")

    status_data = {
        "open_plugin_run_id": open_plugin_run_id,
        "status": status,
    }
    if status == "SUCCEEDED":
        status_data["outputs"] = _open_plugin_v4_outputs(open_plugin_run_id)
    elif status == "FAILED":
        status_data["error_message"] = "demo open plugin failed"

    return _demo_response(data=status_data)


@api_view(["GET", "POST"])
def open_plugin_v4_cancel_api(request, open_plugin_run_id):
    """
    Open Plugin V4 Cancel API - 模拟取消开放插件运行实例。
    """
    return _demo_response(data={"open_plugin_run_id": open_plugin_run_id, "status": "CANCELLED"})
