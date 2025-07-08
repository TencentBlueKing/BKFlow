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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("BKAPP_FLOW_DB_NAME"),  # 外部数据库名
        "USER": os.getenv("BKAPP_FLOW_DB_USER"),  # 外部数据库用户
        "PASSWORD": os.getenv("BKAPP_FLOW_DB_PASSWORD"),  # 外部数据库密码
        "HOST": os.getenv("BKAPP_FLOW_DB_HOST"),  # 外部数据库主机
        "PORT": os.getenv("BKAPP_FLOW_DB_PORT"),  # 外部数据库端口
    },
}


default.logging_addition_settings(LOGGING, environment="prod")
BK_APIGW_STAGE_NAME = "prod"
BKAPP_APIGW_SYNC_STAGE = ["prod"]
CSRF_COOKIE_NAME = APP_CODE + "_csrftoken"

try:
    from module_settings import *  # noqa
except ImportError:
    pass
