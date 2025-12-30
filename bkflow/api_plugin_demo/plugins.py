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
from django.conf import settings


def _build_api_url(request, path):
    """
    构建API URL
    优先使用API网关URL模板，否则使用request构建绝对URL
    """
    try:
        if hasattr(settings, "BK_API_URL_TMPL") and hasattr(settings, "BK_APIGW_NAME"):
            return f"{settings.BK_API_URL_TMPL.format(api_name=settings.BK_APIGW_NAME)}{path}"
    except Exception:
        pass

    # 如果无法使用API网关URL，使用request构建绝对URL
    if request:
        return request.build_absolute_uri(path)
    return path


def get_category_list(scope_type, scope_value):
    """
    获取分类列表
    :param scope_type: 作用域类型
    :param scope_value: 作用域值
    :return: 分类列表
    """
    # 示例：返回两个分类
    return [
        {"name": "基础工具", "id": "basic_tools"},
        {"name": "数据处理", "id": "data_processing"},
    ]


def get_api_list(limit, offset, scope_type, scope_value, category, request=None):
    """
    获取API列表
    :param limit: 每页数量
    :param offset: 偏移量
    :param scope_type: 作用域类型
    :param scope_value: 作用域值
    :param category: 分类ID
    :param request: HTTP请求对象，用于构建URL
    :return: API列表数据
    """
    # 定义所有可用的API
    base_path = "/stage/api_plugin_demo/detail_meta/"
    all_apis = [
        {
            "id": "get_user_info",
            "name": "获取用户信息",
            "category": "basic_tools",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=get_user_info"),
        },
        {
            "id": "create_task",
            "name": "创建任务",
            "category": "basic_tools",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=create_task"),
        },
        {
            "id": "process_data",
            "name": "处理数据",
            "category": "data_processing",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=process_data"),
        },
    ]

    # 根据分类过滤
    if category:
        filtered_apis = [api for api in all_apis if api["category"] == category]
    else:
        filtered_apis = all_apis

    # 分页处理
    total = len(filtered_apis)
    paginated_apis = filtered_apis[offset : offset + limit]

    # 格式化返回数据
    api_list = [
        {
            "id": api["id"],
            "name": api["name"],
            "meta_url": api["meta_url"],
        }
        for api in paginated_apis
    ]

    return {
        "total": total,
        "apis": api_list,
    }


def get_api_detail(api_id, request=None):
    """
    获取API详情元数据
    :param api_id: API ID
    :param request: HTTP请求对象，用于构建URL
    :return: API详情数据
    """
    # API插件1: 获取用户信息 (GET请求示例)
    if api_id == "get_user_info":
        return {
            "id": "get_user_info",
            "name": "获取用户信息",
            "url": _build_api_url(request, "/api/api_plugin_demo/execute/get_user_info/"),
            "methods": ["GET"],
            "inputs": [
                {
                    "key": "username",
                    "name": "用户名",
                    "desc": "要查询的用户名",
                    "required": True,
                    "type": "string",
                    "form_type": "input",
                },
                {
                    "key": "include_details",
                    "name": "包含详细信息",
                    "desc": "是否包含用户的详细信息",
                    "required": False,
                    "type": "bool",
                    "default": False,
                },
            ],
            "outputs": [
                {
                    "key": "user_id",
                    "name": "用户ID",
                    "desc": "用户的唯一标识",
                    "type": "string",
                },
                {
                    "key": "username",
                    "name": "用户名",
                    "desc": "用户名",
                    "type": "string",
                },
                {
                    "key": "email",
                    "name": "邮箱",
                    "desc": "用户邮箱地址",
                    "type": "string",
                },
            ],
        }

    # API插件2: 创建任务 (POST请求示例)
    elif api_id == "create_task":
        return {
            "id": "create_task",
            "name": "创建任务",
            "url": _build_api_url(request, "/api/api_plugin_demo/execute/create_task/"),
            "methods": ["POST"],
            "inputs": [
                {
                    "key": "task_name",
                    "name": "任务名称",
                    "desc": "要创建的任务名称",
                    "required": True,
                    "type": "string",
                    "form_type": "input",
                },
                {
                    "key": "description",
                    "name": "任务描述",
                    "desc": "任务的详细描述",
                    "required": False,
                    "type": "string",
                    "form_type": "textarea",
                },
                {
                    "key": "priority",
                    "name": "优先级",
                    "desc": "任务优先级",
                    "required": True,
                    "type": "string",
                    "form_type": "select",
                    "options": [
                        {"text": "低", "value": "low"},
                        {"text": "中", "value": "medium"},
                        {"text": "高", "value": "high"},
                    ],
                    "default": "medium",
                },
                {
                    "key": "tags",
                    "name": "标签",
                    "desc": "任务标签列表",
                    "required": False,
                    "type": "list",
                    "options": ["urgent", "important", "review", "bug"],
                },
            ],
            "outputs": [
                {
                    "key": "task_id",
                    "name": "任务ID",
                    "desc": "创建的任务的唯一标识",
                    "type": "string",
                },
                {
                    "key": "task_name",
                    "name": "任务名称",
                    "desc": "创建的任务名称",
                    "type": "string",
                },
                {
                    "key": "status",
                    "name": "状态",
                    "desc": "任务状态",
                    "type": "string",
                },
            ],
        }

    # API插件3: 处理数据 (POST请求示例，包含表格输入)
    elif api_id == "process_data":
        return {
            "id": "process_data",
            "name": "处理数据",
            "url": _build_api_url(request, "/api/api_plugin_demo/execute/process_data/"),
            "methods": ["POST"],
            "inputs": [
                {
                    "key": "operation",
                    "name": "操作类型",
                    "desc": "选择要执行的数据处理操作",
                    "required": True,
                    "type": "string",
                    "form_type": "select",
                    "options": [
                        {"text": "汇总", "value": "sum"},
                        {"text": "平均", "value": "avg"},
                        {"text": "最大值", "value": "max"},
                        {"text": "最小值", "value": "min"},
                    ],
                },
                {
                    "key": "data_items",
                    "name": "数据项",
                    "desc": "要处理的数据项列表",
                    "required": True,
                    "type": "list",
                    "form_type": "table",
                    "table": {
                        "meta": {
                            "read_only": False,
                            "import": False,
                            "export": False,
                        },
                        "fields": [
                            {
                                "key": "name",
                                "name": "名称",
                                "desc": "数据项名称",
                                "required": True,
                                "type": "string",
                                "form_type": "input",
                            },
                            {
                                "key": "value",
                                "name": "数值",
                                "desc": "数据项的数值",
                                "required": True,
                                "type": "int",
                            },
                            {
                                "key": "category",
                                "name": "分类",
                                "desc": "数据项分类",
                                "required": False,
                                "type": "string",
                                "form_type": "select",
                                "options": ["A", "B", "C"],
                            },
                        ],
                    },
                },
            ],
            "outputs": [
                {
                    "key": "result",
                    "name": "处理结果",
                    "desc": "数据处理的结果值",
                    "type": "string",
                },
                {
                    "key": "processed_count",
                    "name": "处理数量",
                    "desc": "已处理的数据项数量",
                    "type": "int",
                },
            ],
        }

    return None
