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
