# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging

import tldextract
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

logger = logging.getLogger("root")


def get_top_level_domain(url):
    # 提取域名部分
    extracted = tldextract.extract(url)
    # 拼合主域名和顶级域名，形成一级域名
    top_level_domain = "{}.{}".format(extracted.domain, extracted.suffix)
    return top_level_domain


class DomainValidator(object):
    """域名校验."""
    @staticmethod
    def validate(url):
        """
        return is_valid(bool), err(str)
        """
        if not settings.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK:
            return True, []

        allowed_domains = []
        if not settings.ALLOWED_HTTP_PLUGIN_DOMAINS:
            # 默认只允许访问蓝鲸域名
            allowed_domains = [get_top_level_domain(settings.BK_URL)]
        else:
            allowed_domains = settings.ALLOWED_HTTP_PLUGIN_DOMAINS.split(",")

        for allowed_domain in allowed_domains:
            if get_top_level_domain(url) == allowed_domain:
                return True, []

        return False, allowed_domains


def validate_password_variable_enabled(pipeline_tree):
    """
    校验流程树中是否包含已关闭的密码变量
    当 ENABLE_PASSWORD_VARIABLE 为 False 时，若 constants 中存在 custom_type="password" 的变量则直接报错
    """
    if settings.ENABLE_PASSWORD_VARIABLE:
        return

    constants = pipeline_tree.get("constants", {}) if isinstance(pipeline_tree, dict) else {}
    for key, info in constants.items():
        if isinstance(info, dict) and info.get("custom_type") == "password":
            raise serializers.ValidationError(
                _("密码变量功能已关闭，流程树中不允许使用 custom_type=password 的变量(key={key})").format(key=key)
            )


def validate_no_password_variable_in_apigw(pipeline_tree):
    """
    开放 API 创建任务时禁止包含密码变量。
    密码变量依赖前端使用公钥加密，接入方无法通过开放 API 获取公钥，若传入明文会被原样落库
    并经由 get_task_node_detail 等接口回显，因此显式拒绝含密码变量的任务创建。
    """
    constants = pipeline_tree.get("constants", {}) if isinstance(pipeline_tree, dict) else {}
    for key, info in constants.items():
        if isinstance(info, dict) and info.get("custom_type") == "password":
            raise serializers.ValidationError(
                _("开放API不支持密码变量，请通过页面填写，或移除密码变量 {key} 后重试").format(key=key)
            )
