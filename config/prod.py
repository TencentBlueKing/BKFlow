# -*- coding: utf-8 -*-
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


from config import RUN_VER

if RUN_VER == "open":
    from blueapps.patch.settings_open_saas import *  # noqa

    ESB_SDK_NAME = "packages.blueking.component"
else:
    from blueapps.patch.settings_paas_services import *  # noqa

# 正式环境
RUN_MODE = "PRODUCT"

# 只对正式环境日志级别进行配置，可以在这里修改
# from blueapps.conf.log import set_log_level # noqa
# LOG_LEVEL = "ERROR"
# LOGGING = set_log_level(locals())

# 正式环境数据库可以在这里配置
# DATABASES.update(
#     {
#         'default': {
#             'ENGINE': 'django.db.backends.mysql',
#             'NAME': '',  # 外部数据库名
#             'USER': '',  # 外部数据库用户
#             'PASSWORD': '',  # 外部数据库密码
#             'HOST': '',  # 外部数据库主机
#             'PORT': '',  # 外部数据库端口
#         },
#     }
# )

default.logging_addition_settings(LOGGING, environment="prod")
BK_APIGW_STAGE_NAME = "prod"
BKAPP_APIGW_SYNC_STAGE = ["prod"]
CSRF_COOKIE_NAME = APP_CODE + "_csrftoken"

# Django 4.2 兼容：CSRF 可信来源配置 - 支持 PaaS 容器部署
import os

_csrf_origins_str = os.getenv("BKAPP_CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_str:
    # 自定义环境变量（支持逗号分隔多个域名）
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_origins_str.split(",") if origin.strip()]
else:
    # 使用 PaaS 平台变量
    _bkpaas_url = os.getenv("BKPAAS_URL", "")
    if _bkpaas_url:
        CSRF_TRUSTED_ORIGINS = [_bkpaas_url]
        if _bkpaas_url.startswith("https://"):
            CSRF_TRUSTED_ORIGINS.append(_bkpaas_url.replace("https://", "http://", 1))
        elif _bkpaas_url.startswith("http://"):
            CSRF_TRUSTED_ORIGINS.append(_bkpaas_url.replace("http://", "https://", 1))
    else:
        CSRF_TRUSTED_ORIGINS = []

# Django 4.2 兼容：允许的主机名（生产环境应严格限制）
# 完全从环境变量读取，无硬编码
_allowed_hosts_str = os.getenv("BKAPP_ALLOWED_HOSTS", "")
if _allowed_hosts_str:
    ALLOWED_HOSTS = [host.strip() for host in _allowed_hosts_str.split(",") if host.strip()]
else:
    # 从 BKPAAS_URL 提取域名
    _bkpaas_url = os.getenv("BKPAAS_URL", "")
    if _bkpaas_url:
        from urllib.parse import urlparse
        parsed = urlparse(_bkpaas_url)
        if parsed.netloc:
            ALLOWED_HOSTS = [parsed.netloc, ".bktencent.com"]
        else:
            ALLOWED_HOSTS = []
    else:
        ALLOWED_HOSTS = []

try:
    from module_settings import *  # noqa
except ImportError:
    pass
