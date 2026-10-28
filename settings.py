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

import os

import pymysql

import env
from bkflow.utils.mysql57_compat import configure_mysql57_compat

pymysql.install_as_MySQLdb()

"""
请不要修改该文件
如果你需要对settings里的内容做修改，config/default.py 文件中 添加即可
如有任何疑问，请联系 【蓝鲸助手】
"""


# V3判断环境的环境变量为BKPAAS_ENVIRONMENT
if "BKPAAS_ENVIRONMENT" in os.environ:
    ENVIRONMENT = os.getenv("BKPAAS_ENVIRONMENT", "dev")
# V2判断环境的环境变量为BK_ENV
else:
    PAAS_V2_ENVIRONMENT = os.environ.get("BK_ENV", "development")
    ENVIRONMENT = {"development": "dev", "testing": "stag", "production": "prod"}.get(PAAS_V2_ENVIRONMENT)
DJANGO_CONF_MODULE = "config.{env}".format(env=ENVIRONMENT)

try:
    _module = __import__(DJANGO_CONF_MODULE, globals(), locals(), ["*"])
except ImportError as err:
    raise ImportError("Could not import config '{}' (Is it on sys.path?): {}".format(DJANGO_CONF_MODULE, err))

for _setting in dir(_module):
    if _setting == _setting.upper():
        locals()[_setting] = getattr(_module, _setting)

# 在 Django 初始化连接配置前注册统计库，确保默认字段和 MySQL 后端适配覆盖所有连接。
DATABASES = _module.DATABASES.copy()
if env.STATISTICS_DB_HOST and env.STATISTICS_DB_NAME:
    DATABASES["statistics"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env.STATISTICS_DB_NAME,
        "USER": env.STATISTICS_DB_USER,
        "PASSWORD": env.STATISTICS_DB_PASSWORD,
        "HOST": env.STATISTICS_DB_HOST,
        "PORT": env.STATISTICS_DB_PORT,
    }

# 在平台、模块和本地配置加载完毕后统一处理，覆盖 interface 和独立 engine 的连接。
DATABASES = configure_mysql57_compat(DATABASES)
