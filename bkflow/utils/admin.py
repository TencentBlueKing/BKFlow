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


def get_admin_username():
    """
    获取系统默认管理员用户名

    返回系统配置的管理员用户名，支持通过环境变量进行配置，未配置时返回默认值 "admin"

    环境变量配置（优先级从高到低）：
        1. BK_ADMIN_USERNAME - 标准大写命名（兼容配置）
        2. bkAdminUsername - 小驼峰命名（项目约定，PaaS 平台规范）

    实现说明：
        从 settings.BK_ADMIN_USERNAME 读取，该值在 env.py 中从环境变量加载

    Returns:
        str: 管理员用户名

    """
    return getattr(settings, "BK_ADMIN_USERNAME", "admin")


def is_admin_username(username):
    """
    判断给定的用户名是否是系统管理员

    兼容当前配置的管理员和历史遗留值（admin, bk_admin）

    Args:
        username (str): 要检查的用户名

    Returns:
        bool: 如果是系统管理员返回 True，否则返回 False

    """
    if not username:
        return False

    current_admin = get_admin_username()

    # 1. 匹配当前配置的管理员
    if username == current_admin:
        return True

    # 2. 兼容历史遗留值
    legacy_admins = ["admin", "bk_admin"]
    if username in legacy_admins:
        return True

    return False
