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

from blueapps.conf.validators import EnvValidator

from config import RUN_VER
from config.default import FRONTEND_BACKEND_SEPARATION

EnvValidator(RUN_VER).validate()

if RUN_VER == "open":
    from blueapps.patch.settings_open_saas import *  # noqa

    ESB_SDK_NAME = "packages.blueking.component"
else:
    from blueapps.patch.settings_paas_services import *  # noqa

# 本地开发环境
RUN_MODE = "DEVELOP"

# 自定义本地环境日志级别
# from blueapps.conf.log import set_log_level # noqa
# LOG_LEVEL = "DEBUG"
# LOGGING = set_log_level(locals())

# APP本地静态资源目录
STATIC_URL = "/static/"

# APP静态资源目录url
# REMOTE_STATIC_URL = '%sremote/' % STATIC_URL

# Celery 消息队列设置 RabbitMQ
BROKER_URL = "amqp://guest:guest@localhost:5672/"
# Celery 消息队列设置 Redis
# BROKER_URL = "redis://localhost:6379/0"

# DEBUG = True

# 本地开发数据库设置
# USE FOLLOWING SQL TO CREATE THE DATABASE NAMED APP_CODE
# SQL: CREATE DATABASE `sops-engine-svct` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci; # noqa: E501
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": APP_CODE,  # noqa
        "USER": "root",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "3306",
    },
}

CSRF_COOKIE_NAME = APP_CODE + "_csrftoken"

# 前后端开发模式下支持跨域配置
if FRONTEND_BACKEND_SEPARATION:
    INSTALLED_APPS += ("corsheaders",)
    # 该跨域中间件需要放在前面
    MIDDLEWARE = ("corsheaders.middleware.CorsMiddleware",) + MIDDLEWARE
    CORS_ORIGIN_ALLOW_ALL = True
    CORS_ALLOW_CREDENTIALS = True

default.logging_addition_settings(LOGGING, environment="dev")

try:
    from module_settings import *  # noqa
except ImportError:
    pass

# 多人开发时，无法共享的本地配置可以放到新建的 local_settings.py 文件中
# 并且把 local_settings.py 加入版本管理忽略文件中
try:
    from local_settings import *  # noqa
except ImportError:
    pass
