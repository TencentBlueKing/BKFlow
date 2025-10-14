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
import json
import os

# 部署模块相关变量
# 是否开启部分调试日志
ENABLE_DEBUG_LOG = bool(int(os.getenv("ENABLE_DEBUG_LOG", 0)))

# 模块类型，合法值详见 BKFLOWModuleType
BKFLOW_MODULE_TYPE = os.getenv("BKFLOW_MODULE_TYPE")
BKFLOW_MODULE_CODE = os.getenv("BKFLOW_MODULE_CODE")
# 资源隔离级别，合法值详见 BKFLOWResourceIsolationLevel
BKFLOW_RESOURCE_ISOLATION_LEVEL = os.getenv("BKFLOW_RESOURCE_ISOLATION_LEVEL")
BKFLOW_CELERY_BROKER_URL = os.getenv("BKFLOW_CELERY_BROKER_URL", "")
BKFLOW_DATABASE_ENGINE = os.getenv("BKFLOW_DATABASE_ENGINE", "django.db.backends.mysql")
BKFLOW_DATABASE_NAME = os.getenv("BKFLOW_DATABASE_NAME")
BKFLOW_DATABASE_USER = os.getenv("BKFLOW_DATABASE_USER")
BKFLOW_DATABASE_PASSWORD = os.getenv("BKFLOW_DATABASE_PASSWORD", "")
BKFLOW_DATABASE_HOST = os.getenv("BKFLOW_DATABASE_HOST")
BKFLOW_DATABASE_PORT = os.getenv("BKFLOW_DATABASE_PORT")

# CELERY 相关配置
BK_CELERYD_CONCURRENCY = int(os.getenv("BK_CELERYD_CONCURRENCY", 2))
# 是否允许 celery worker 发送监控事件
CELERY_SEND_EVENTS = bool(os.getenv("CELERY_SEND_EVENTS", False))
CELERY_BROKER_POOL_LIMIT = int(os.getenv("CELERY_BROKER_POOL_LIMIT", 10))

# REDIS 相关配置
BKAPP_REDIS_HOST = os.getenv("REDIS_HOST")
BKAPP_REDIS_PORT = os.getenv("REDIS_PORT")
BKAPP_REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
BKAPP_REDIS_SERVICE_NAME = os.getenv("REDIS_SERVICE_NAME")
BKAPP_REDIS_MODE = os.getenv("REDIS_MODE")
BKAPP_REDIS_DB = os.getenv("REDIS_DB")
BKAPP_REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD")

# 模块间调用相关配置
APP_INTERNAL_VALIDATION_SKIP = bool(os.getenv("APP_INTERNAL_VALIDATION_SKIP", False))
# 本模块被调用允许通过的 token
APP_INTERNAL_TOKEN = os.getenv("APP_INTERNAL_TOKEN", "")
# 任务模块调用 Interface 模块的 token
INTERFACE_APP_INTERNAL_TOKEN = os.getenv("INTERFACE_APP_INTERNAL_TOKEN", "")
# 任务模块调用 Interface 模块的 url
INTERFACE_APP_URL = os.getenv("INTERFACE_APP_URL", "")
# TOKEN保留时间，默认半天
TOKEN_RETENTION_TIME = int(os.getenv("TOKEN_RETENTION_TIME", 12 * 60 * 60))

# 变量名关键字黑名单
VARIABLE_KEY_BLACKLIST = os.getenv("BKAPP_VARIABLE_KEY_BLACKLIST", "context,")

# APIGW 访问地址
BK_APIGW_URL_TMPL = os.getenv("BK_API_URL_TMPL") or os.getenv("BK_COMPONENT_API_URL")
BK_APIGW_NAME = os.getenv("BK_APIGW_NAME", "").replace("_", "-")
# 用于校验网关地址是否合法，形如^(?P<api_name>[\w-]+)\.xxx.com
BK_APIGW_NETLOC_PATTERN = os.getenv("BK_APIGW_NETLOC_PATTERN")

BK_ITSM_API_ENTRY = os.getenv("BK_ITSM_API_ENTRY")

# CALLBACK 回调入口，处理走网关回调的场景
BKAPP_INNER_CALLBACK_ENTRY = os.getenv("BKAPP_INNER_CALLBACK_ENTRY", "")

# 默认引擎模块入口
BKAPP_DEFAULT_ENGINE_MODULE_ENTRY = os.getenv("BKAPP_DEFAULT_ENGINE_MODULE_ENTRY", "")

# 默认引擎插件超时时间
BKAPP_API_PLUGIN_REQUEST_TIMEOUT = int(os.getenv("BKAPP_API_PLUGIN_REQUEST_TIMEOUT", 30))

CALLBACK_KEY = os.getenv("BKFLOW_DEFAULT_CALLBACK_KEY", "").encode("utf-8")

BK_PAAS_ESB_HOST = os.getenv("BK_COMPONENT_API_URL", "")

PAASV3_APIGW_API_TOKEN = os.getenv("BKAPP_PAASV3_APIGW_API_TOKEN")

# 启动节点日志数据源拉取
NODE_LOG_DATA_SOURCE = os.getenv("NODE_LOG_DATA_SOURCE", "DATABASE")
NODE_LOG_DATA_SOURCE_CONFIG = json.loads(os.getenv("NODE_LOG_DATA_SOURCE_CONFIG", "{}"))
LOG_PERSISTENT_DAYS = int(os.getenv("LOG_PERSISTENT_DAYS", 7))

ENABLE_OTEL_TRACE = os.getenv("BKAPP_ENABLE_OTEL_TRACE", True if os.getenv("OTEL_BK_DATA_TOKEN") else False)

BKAPP_LOG_SHIELDING_KEYWORDS = os.getenv("BKAPP_LOG_SHIELDING_KEYWORDS", "")

MEMBER_SELECTOR_DATA_HOST = os.getenv("MEMBER_SELECTOR_DATA_HOST", os.getenv("BK_COMPONENT_API_URL", ""))

# 蓝鲸插件授权过滤 APP
PLUGIN_DISTRIBUTOR_NAME = os.getenv("PLUGIN_DISTRIBUTOR_NAME", os.getenv("BKAPP_PLUGIN_DISTRIBUTOR_NAME"))

# 跳过 APIGW 校验
SKIP_APIGW_CHECK = bool(os.getenv("SKIP_APIGW_CHECK", False))
BK_APIGW_REQUIRE_EXEMPT = bool(os.getenv("BK_APIGW_REQUIRE_EXEMPT", False))

# 网关管理员
BK_APIGW_MANAGER_MAINTAINERS = os.getenv("BK_APIGW_MANAGER_MAINTAINERS", "admin").split(",")
BK_APIGW_GRANT_APPS = os.getenv("BK_APIGW_GRANT_APPS").split(",") if os.getenv("BK_APIGW_GRANT_APPS") else []

# APIGW API SERVER服务地址
BKAPP_APIGW_API_HOST = os.getenv("BKAPP_APIGW_API_HOST", "")

# bk notice settings
DISABLE_REGISTER_BKFLOW_TO_BKNOTICE = bool(os.getenv("DISABLE_REGISTER_BKFLOW_TO_BKNOTICE", False))

# ban 掉 admin 权限
BLOCK_ADMIN_PERMISSION = bool(os.getenv("BLOCK_ADMIN_PERMISSION", False))

# BKPAAS 相关环境变量
BKPAAS_ENGINE_REGION = os.getenv("BKPAAS_ENGINE_REGION", "default")  # default = open
BKPAAS_DOMAIN = os.getenv("BKPAAS_BK_DOMAIN", "")

# 空间配置
MAX_SPACE_NUM_PER_APP = int(os.getenv("BKAPP_MAX_SPACE_NUM_PER_APP", 100))

BKPAAS_SHARED_RES_URL = os.getenv("BKPAAS_SHARED_RES_URL", "")

BKFLOW_LOGIN_URL = os.getenv("BKAPP_LOGIN_URL", "") or os.getenv("BKPAAS_LOGIN_URL", "")

# 报错联系助手链接
MESSAGE_HELPER_URL = os.getenv("BKAPP_MESSAGE_HELPER_URL", "")

# 获取 PaaS 注入的蓝鲸域名
BKPAAS_BK_DOMAIN = os.getenv("BKPAAS_BK_DOMAIN", "") or os.getenv("BK_DOMAIN", "")

# 文档中心链接
BK_DOC_CENTER_HOST = os.getenv("BK_DOC_CENTER_HOST", os.getenv("BK_DOCS_URL_PREFIX", "")).rstrip("/")

# APP 白名单
APP_WHITE_LIST_STR = os.getenv("BKAPP_APP_WHITE_LIST", "")  # 逗号分隔的字符串

# 系统空间插件列表
SPACE_PLUGIN_LIST_STR = os.getenv("SPACE_PLUGIN_LIST_STR", "")  # 逗号分隔的字符串

# 是否支持API插件使用 BKFLOW 凭证
USE_BKFLOW_CREDENTIAL = os.getenv("USE_BKFLOW_CREDENTIAL", False)  # 默认关闭使用

# 是否开启使用pyinstrument
USE_PYINSTRUMENT = os.getenv("USE_PYINSTRUMENT", False)

# 清理任务批量数目
CLEAN_TASK_BATCH_NUM = os.getenv("CLEAN_TASK_BATCH_NUM", 200)

# 清理节点批量数目
CLEAN_TASK_NODE_BATCH_NUM = os.getenv("CLEAN_TASK_NODE_BATCH_NUM", 5000)

# 是否开启清理任务 默认关闭
ENABLE_CLEAN_TASK = os.getenv("ENABLE_CLEAN_TASK", False)

# 清理任务保存周期 默认 30 天
CLEAN_TASK_EXPIRED_DAYS = int(os.getenv("CLEAN_TASK_EXPIRED_DAYS", 180))

# 清理任务周期 默认 5 分钟一次
CLEAN_TASK_CRONTAB = os.getenv("CLEAN_TASK_CRONTAB", "*/5 * * * *")

# 是否开启蓝鲸插件二次授权检查
ENABLE_BK_PLUGIN_AUTHORIZATION = os.getenv("ENABLE_BK_PLUGIN_AUTHORIZATION", False)  # 暂时关闭使用
# 蓝鲸插件同步频率，默认 10 分钟一次
SYNC_BK_PLUGINS_CRONTAB = os.getenv("SYNC_BK_PLUGINS_INTERVAL", "*/10 * * * *")

# 允许的HTTP插件域名
ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = bool(int(os.getenv("ENABLE_HTTP_PLUGIN_DOMAINS_CHECK", 1)))
ALLOWED_HTTP_PLUGIN_DOMAINS = os.getenv("ALLOWED_HTTP_PLUGIN_DOMAINS", "")

# bamboo engine 配置
PIPELINE_RERUN_MAX_TIMES = int(os.getenv("PIPELINE_RERUN_MAX_TIMES", 100))
BAMBOO_DJANGO_ERI_NODE_RERUN_LIMIT = int(os.getenv("BAMBOO_DJANGO_ERI_NODE_RERUN_LIMIT", 100))
