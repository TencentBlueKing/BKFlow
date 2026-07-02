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


def _get_api_plugin_demo_stage():
    """获取 APIGW 对外暴露的环境路径。"""
    return getattr(settings, "BK_APIGW_STAGE_NAME", "") or getattr(settings, "ENVIRONMENT", "") or "stage"


def _build_api_plugin_demo_path(path):
    """构建 api_plugin_demo 对外访问路径。"""
    return "/{}/api_plugin_demo/{}".format(_get_api_plugin_demo_stage(), path.lstrip("/"))


OPEN_PLUGIN_V4_WRAPPER_VERSION = "v4.0.0"


OPEN_PLUGIN_V4_DEMOS = {
    "demo_polling_job": {
        "id": "demo_polling_job",
        "name": "V4 Polling Demo 作业",
        "category": "open_plugin_v4",
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
        "category": "open_plugin_v4",
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


def get_open_plugin_v4_api_config(api_id):
    """获取 v4 open plugin demo 配置。"""
    config = OPEN_PLUGIN_V4_DEMOS.get(api_id)
    return copy.deepcopy(config) if config else None


def get_open_plugin_v4_api_list(limit, offset, scope_type, scope_value, category, request=None):
    """
    获取 uniform_api v4.0.0 open plugin demo 列表。
    :param limit: 每页数量
    :param offset: 偏移量
    :param scope_type: 作用域类型
    :param scope_value: 作用域值
    :param category: 分类 ID
    :param request: HTTP 请求对象，用于构建 URL
    :return: API 列表数据
    """
    api_items = list(OPEN_PLUGIN_V4_DEMOS.values())
    if category:
        api_items = [api for api in api_items if api["category"] == category]

    total = len(api_items)
    paginated_apis = api_items[offset : offset + limit]
    api_list = []
    for api in paginated_apis:
        detail_path = _build_api_plugin_demo_path(
            "open_plugin_v4/detail_meta/?api_id={}&version={{version}}".format(api["id"])
        )
        api_list.append(
            {
                "id": api["id"],
                "name": api["name"],
                "plugin_source": api["plugin_source"],
                "plugin_code": api["plugin_code"],
                "wrapper_version": OPEN_PLUGIN_V4_WRAPPER_VERSION,
                "default_version": api["default_version"],
                "latest_version": api["latest_version"],
                "versions": copy.deepcopy(api["versions"]),
                "meta_url_template": _build_api_url(request, detail_path),
                "category": api["category"],
                "description": api["description"],
            }
        )

    return {"total": total, "apis": api_list}


def get_open_plugin_v4_api_detail(api_id, version=None, request=None):
    """
    获取 uniform_api v4.0.0 open plugin demo 详情。
    :param api_id: API ID
    :param version: 子插件业务版本
    :param request: HTTP 请求对象，用于构建 URL
    :return: API 详情数据
    """
    api = get_open_plugin_v4_api_config(api_id)
    if not api:
        return None

    plugin_version = version or api["default_version"]
    if plugin_version not in api["versions"]:
        raise ValueError("open plugin demo [{}] version [{}] not found".format(api_id, plugin_version))

    detail = {
        "id": api["id"],
        "name": api["name"],
        "desc": api["description"],
        "description": api["description"],
        "plugin_source": api["plugin_source"],
        "plugin_code": api["plugin_code"],
        "plugin_version": plugin_version,
        "wrapper_version": OPEN_PLUGIN_V4_WRAPPER_VERSION,
        "url": _build_api_url(request, _build_api_plugin_demo_path("open_plugin_v4/execute/")),
        "methods": ["POST"],
        "inputs": copy.deepcopy(api["inputs"]),
        "outputs": copy.deepcopy(api["outputs"]),
    }

    if api["schedule_mode"] == "polling":
        detail["polling"] = {
            "url": _build_api_url(request, _build_api_plugin_demo_path("open_plugin_v4/status/")),
            "task_tag_key": "open_plugin_run_id",
            "success_tag": {"key": "status", "value": "SUCCEEDED", "data_key": "outputs"},
            "fail_tag": {"key": "status", "value": "FAILED", "msg_key": "error_message"},
            "running_tag": {"key": "status", "value": "RUNNING"},
        }
    elif api["schedule_mode"] == "callback":
        detail["callback"] = {"enabled": True}

    return detail


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
            "version": "v3.0.0",
        },
        {
            "id": "create_task",
            "name": "创建任务",
            "category": "basic_tools",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=create_task"),
            "version": "v3.0.0",
        },
        {
            "id": "process_data",
            "name": "处理数据",
            "category": "data_processing",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=process_data"),
            "version": "v2.0.0",
        },
        {
            "id": "api_with_credential",
            "name": "使用自定义凭证的API",
            "category": "basic_tools",
            "meta_url": _build_api_url(request, f"{base_path}?api_id=api_with_credential"),
            "version": "v3.0.0",
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
            "version": api["version"],
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
            "version": "v3.0.0",  # 指定使用的uniform_api插件版本
            "url": _build_api_url(request, "/stage/api_plugin_demo/execute/get_user_info/"),
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
            "version": "v3.0.0",  # 指定使用的uniform_api插件版本
            "url": _build_api_url(request, "/stage/api_plugin_demo/execute/create_task/"),
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
            "version": "v2.0.0",  # 指定使用的uniform_api插件版本（示例：使用v2.0.0版本）
            "url": _build_api_url(request, "/stage/api_plugin_demo/execute/process_data/"),
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

    # API插件4: 使用自定义凭证的API (演示credential_key功能)
    elif api_id == "api_with_credential":
        return {
            "id": "api_with_credential",
            "name": "使用自定义凭证的API",
            "version": "v3.0.0",  # 必须使用v3.0.0版本才支持credential_key
            "url": _build_api_url(request, "/stage/api_plugin_demo/execute/api_with_credential/"),
            "methods": ["POST"],
            "credential_key": "custom_app_credential",  # 声明使用 custom_app_credential 凭证
            "inputs": [
                {
                    "key": "resource_id",
                    "name": "资源ID",
                    "desc": "要操作的资源ID",
                    "required": True,
                    "type": "string",
                    "form_type": "input",
                },
                {
                    "key": "action",
                    "name": "操作类型",
                    "desc": "要执行的操作",
                    "required": True,
                    "type": "string",
                    "form_type": "select",
                    "options": [
                        {"text": "创建", "value": "create"},
                        {"text": "更新", "value": "update"},
                        {"text": "删除", "value": "delete"},
                    ],
                    "default": "create",
                },
            ],
            "outputs": [
                {
                    "key": "resource_id",
                    "name": "资源ID",
                    "desc": "操作的资源ID",
                    "type": "string",
                },
                {
                    "key": "action",
                    "name": "操作类型",
                    "desc": "执行的操作",
                    "type": "string",
                },
                {
                    "key": "status",
                    "name": "状态",
                    "desc": "操作状态",
                    "type": "string",
                },
                {
                    "key": "message",
                    "name": "消息",
                    "desc": "操作结果消息",
                    "type": "string",
                },
            ],
        }

    return None
