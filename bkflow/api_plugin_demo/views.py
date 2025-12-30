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
)


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
