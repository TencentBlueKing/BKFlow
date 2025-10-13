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

import base64
import datetime
import json

from bamboo_engine.config import Settings as BambooSettings
from blueapps.conf.default_settings import *  # noqa
from blueapps.conf.log import get_logging_config_dict
from blueapps.opentelemetry.utils import inject_logging_trace_info

import env
from bkflow.utils.pipeline import pipeline_gateway_expr_func

# 这里是默认的 INSTALLED_APPS，大部分情况下，不需要改动
# 如果你已经了解每个默认 APP 的作用，确实需要去掉某些 APP，请去掉下面的注释，然后修改
# INSTALLED_APPS = (
#     'bkoauth',
#     # 框架自定义命令
#     'blueapps.contrib.bk_commands',
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.sites',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',
#     # account app
#     'blueapps.account',
# )

# 这里是默认的中间件，大部分情况下，不需要改动
# 如果你已经了解每个默认 MIDDLEWARE 的作用，确实需要去掉某些 MIDDLEWARE，或者改动先后顺序，请去掉下面的注释，然后修改
# MIDDLEWARE = (
#     # request instance provider
#     'blueapps.middleware.request_provider.RequestProvider',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     # 跨域检测中间件， 默认关闭
#     # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'django.middleware.security.SecurityMiddleware',
#     # 蓝鲸静态资源服务
#     'whitenoise.middleware.WhiteNoiseMiddleware',
#     # Auth middleware
#     'blueapps.account.middlewares.RioLoginRequiredMiddleware',
#     'blueapps.account.middlewares.WeixinLoginRequiredMiddleware',
#     'blueapps.account.middlewares.LoginRequiredMiddleware',
#     # exception middleware
#     'blueapps.core.exceptions.middleware.AppExceptionMiddleware',
#     # django国际化中间件
#     'django.middleware.locale.LocaleMiddleware',
# )
# 自定义中间件
MIDDLEWARE = (
    "bkflow.utils.middlewares.TraceIDInjectMiddleware",
    "bkflow.utils.middlewares.ExceptionMiddleware",
    "bkflow.utils.middlewares.AppInfoInjectMiddleware",
) + MIDDLEWARE

if env.USE_PYINSTRUMENT:
    MIDDLEWARE += ("pyinstrument.middleware.ProfilerMiddleware",)

# 是否开启调试日志
ENABLE_DEBUG_LOG = env.ENABLE_DEBUG_LOG

# 模块间调用相关配置
APP_INTERNAL_VALIDATION_SKIP = env.APP_INTERNAL_VALIDATION_SKIP
APP_INTERNAL_TOKEN = env.APP_INTERNAL_TOKEN
APP_INTERNAL_TOKEN_HEADER_KEY = "Bkflow-Internal-Token"
APP_INTERNAL_SPACE_ID_HEADER_KEY = "Bkflow-Internal-Space-Id"
APP_INTERNAL_FROM_SUPERUSER_HEADER_KEY = "Bkflow-Internal-From-SuperUser"
APP_INTERNAL_TOKEN_REQUEST_META_KEY = "HTTP_BKFLOW_INTERNAL_TOKEN"
TOKEN_RETENTION_TIME = env.TOKEN_RETENTION_TIME

APP_WHITE_LIST = env.APP_WHITE_LIST_STR.split(",") if env.APP_WHITE_LIST_STR else []

# PAAS SERVICE DETECTION
BKPAAS_SERVICE_ADDRESSES_BKSAAS = os.getenv("BKPAAS_SERVICE_ADDRESSES_BKSAAS")
BKSAAS_DEFAULT_MODULE_NAME = "default"
BKFLOW_DEFAULT_ENGINE_MODULE_NAME = "default-engine"
BK_SAAS_HOSTS_DICT = (
    json.loads(base64.b64decode(BKPAAS_SERVICE_ADDRESSES_BKSAAS).decode("utf-8"))
    if BKPAAS_SERVICE_ADDRESSES_BKSAAS
    else {}
)
BK_SAAS_HOSTS = {}
for item in BK_SAAS_HOSTS_DICT:
    BK_SAAS_HOSTS.setdefault(item["key"]["bk_app_code"], {})
    BK_SAAS_HOSTS[item["key"]["bk_app_code"]][item["key"]["module_name"] or BKSAAS_DEFAULT_MODULE_NAME] = item["value"][
        os.getenv("BKPAAS_ENVIRONMENT", "prod")
    ]

# 内部服务回调地址
BKAPP_INNER_CALLBACK_ENTRY = env.BKAPP_INNER_CALLBACK_ENTRY or BK_SAAS_HOSTS.get(APP_CODE, {}).get(
    BKSAAS_DEFAULT_MODULE_NAME, ""
)

# 默认引擎模块地址
BKAPP_DEFAULT_ENGINE_MODULE_ENTRY = env.BKAPP_DEFAULT_ENGINE_MODULE_ENTRY or BK_SAAS_HOSTS.get(APP_CODE, {}).get(
    BKFLOW_DEFAULT_ENGINE_MODULE_NAME, ""
)

# 节点超时最长配置时间
MAX_NODE_EXECUTE_TIMEOUT = 60 * 60 * 24

# 人员选择起拉取数据的host
MEMBER_SELECTOR_DATA_HOST = env.MEMBER_SELECTOR_DATA_HOST

# 蓝鲸插件授权过滤 APP
PLUGIN_DISTRIBUTOR_NAME = env.PLUGIN_DISTRIBUTOR_NAME or APP_CODE

# 默认数据库AUTO字段类型
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# pipeline settings
PIPELINE_TEMPLATE_CONTEXT = "bkflow.template.context.get_template_context"
PIPELINE_INSTANCE_CONTEXT = "bkflow.task.context.get_task_context"
UUID_DIGIT_STARTS_SENSITIVE = True
PIPELINE_EXCLUSIVE_GATEWAY_EXPR_FUNC = pipeline_gateway_expr_func

# pipeline mako render settings
MAKO_SANDBOX_SHIELD_WORDS = [
    "ascii",
    "bytearray",
    "bytes",
    "callable",
    "chr",
    "classmethod",
    "compile",
    "delattr",
    "dir",
    "divmod",
    "exec",
    "eval",
    "filter",
    "frozenset",
    "getattr",
    "globals",
    "hasattr",
    "hash",
    "help",
    "id",
    "input",
    "isinstance",
    "issubclass",
    "iter",
    "locals",
    "map",
    "memoryview",
    "next",
    "object",
    "open",
    "print",
    "property",
    "repr",
    "setattr",
    "staticmethod",
    "super",
    "type",
    "vars",
    "__import__",
]
BambooSettings.MAKO_SANDBOX_SHIELD_WORDS = MAKO_SANDBOX_SHIELD_WORDS
MAKO_SANDBOX_IMPORT_MODULES = {
    "datetime": "datetime",
    "re": "re",
    "hashlib": "hashlib",
    "random": "random",
    "time": "time",
    "os.path": "os.path",
    "config.mock.mock_json": "json",
}
BambooSettings.MAKO_SANDBOX_IMPORT_MODULES = MAKO_SANDBOX_IMPORT_MODULES
# 支持 mako 表达式在 dict/list/tuple 情况下嵌套索引
BambooSettings.ENABLE_RENDER_OBJ_BY_MAKO_STRING = True

# 所有环境的日志级别可以在这里配置
# LOG_LEVEL = 'INFO'

# 两个模块公共用到的 settings 变量
BK_PAAS_ESB_HOST = env.BK_PAAS_ESB_HOST
SKIP_APIGW_CHECK = env.SKIP_APIGW_CHECK
BK_APIGW_NETLOC_PATTERN = (
    env.BK_APIGW_NETLOC_PATTERN
    if env.BKPAAS_ENGINE_REGION == "ieod"
    else env.BK_APIGW_NETLOC_PATTERN.format(hostname=env.BKPAAS_DOMAIN)
)

# 第三方插件
PAASV3_APIGW_API_HOST = env.BK_APIGW_URL_TMPL.format(
    api_name="paasv3" if env.BKPAAS_ENGINE_REGION == "ieod" else "bkpaas3"
)
PLUGIN_APIGW_API_HOST_FORMAT = env.BK_APIGW_URL_TMPL

# 允许的HTTP插件域名
ENABLE_HTTP_PLUGIN_DOMAINS_CHECK = env.ENABLE_HTTP_PLUGIN_DOMAINS_CHECK
ALLOWED_HTTP_PLUGIN_DOMAINS = env.ALLOWED_HTTP_PLUGIN_DOMAINS

# 忽略 example 插件
ENABLE_EXAMPLE_COMPONENTS = False

# 特定空间插件列表
SPACE_PLUGIN_LIST = env.SPACE_PLUGIN_LIST_STR.split(",") if env.SPACE_PLUGIN_LIST_STR else []

# 静态资源文件(js,css等）在APP上线更新后, 由于浏览器有缓存,
# 可能会造成没更新的情况. 所以在引用静态资源的地方，都把这个加上
# Django 模板中：<script src="/a.js?v="></script>
# 如果静态资源修改了以后，上线前改这个版本号即可
STATIC_VERSION = "1.0.0"
DEPLOY_DATETIME = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# CELERY 开关，使用时请改为 True，修改项目目录下的 Procfile 文件，添加以下两行命令：
# worker: python manage.py celery worker -l info
# beat: python manage.py celery beat -l info
# 不使用时，请修改为 False，并删除项目目录下的 Procfile 文件中 celery 配置
IS_USE_CELERY = True

# 前后端分离开发配置开关，设置为True时dev和stag环境会自动加载允许跨域的相关选项
FRONTEND_BACKEND_SEPARATION = False

# CELERY 并发数，默认为 2，可以通过环境变量或者 Procfile 设置
CELERYD_CONCURRENCY = env.BK_CELERYD_CONCURRENCY
CELERY_SEND_EVENTS = env.CELERY_SEND_EVENTS

# CELERY与RabbitMQ增加60秒心跳设置项
BROKER_HEARTBEAT = 60
BROKER_POOL_LIMIT = env.CELERY_BROKER_POOL_LIMIT

# CELERY 配置，申明任务的文件路径，即包含有 @task 装饰器的函数文件
CELERY_IMPORTS = ()

# log level setting
LOG_LEVEL = "INFO"

# load logging settings
LOGGING = get_logging_config_dict(locals())

# keywords to shield in node log
LOG_SHIELDING_KEYWORDS = SECRET_KEY + "," + env.BKAPP_LOG_SHIELDING_KEYWORDS
LOG_SHIELDING_KEYWORDS = LOG_SHIELDING_KEYWORDS.strip().strip(",").split(",") if LOG_SHIELDING_KEYWORDS else []


# SaaS统一日志配置
def logging_addition_settings(logging_dict: dict, environment="prod"):
    # formatters
    logging_dict["formatters"]["light"] = {"format": "%(message)s"}
    logging_dict["formatters"]["engine"] = {"format": "[%(asctime)s][%(levelname)s] %(message)s"}

    # handlers
    logging_dict["handlers"]["pipeline_engine_context"] = {
        "class": "pipeline.log.handlers.EngineContextLogHandler",
        "formatter": "light",
    }

    logging_dict["handlers"]["bamboo_engine_context"] = {
        "class": "pipeline.eri.log.EngineContextLogHandler",
        "formatter": "engine",
    }

    logging_dict["handlers"]["engine"] = {
        "class": "pipeline.log.handlers.EngineLogHandler",
        "formatter": "light",
    }

    logging_dict["handlers"]["pipeline_eri"] = {
        "class": "pipeline.eri.log.ERINodeLogHandler",
        "formatter": "engine",
    }

    # loggers
    logging_dict["loggers"]["component"] = {
        "handlers": ["component", "pipeline_engine_context", "bamboo_engine_context"],
        "level": "INFO",
        "propagate": True,
    }

    logging_dict["loggers"]["root"] = {
        "handlers": ["root", "pipeline_engine_context", "bamboo_engine_context"],
        "level": "INFO",
        "propagate": True,
    }

    logging_dict["loggers"]["pipeline.logging"] = {
        "handlers": ["engine"],
        "level": "INFO",
        "propagate": True,
    }

    logging_dict["loggers"]["pipeline"] = {"handlers": ["root"], "level": "INFO", "propagate": True}

    logging_dict["loggers"]["pipeline.eri.log"] = {"handlers": ["pipeline_eri"], "level": "INFO", "propagate": True}

    logging_dict["loggers"]["bamboo_engine"] = {
        "handlers": ["root", "bamboo_engine_context"],
        "level": "INFO",
        "propagate": True,
    }

    logging_dict["loggers"]["pipeline_engine"] = {
        "handlers": ["root", "pipeline_engine_context"],
        "level": "INFO",
        "propagate": True,
    }

    logging_dict["loggers"]["bk-monitor-report"] = {
        "handlers": ["root"],
        "level": "INFO",
        "propagate": True,
    }

    # 对于不开启数据库日志记录的情况，进行统一处理
    if env.NODE_LOG_DATA_SOURCE != "DATABASE":
        for logger_config in logging_dict["loggers"].values():
            logger_config["handlers"] = [
                handler
                for handler in logger_config["handlers"]
                if handler not in ["pipeline_engine_context", "bamboo_engine_context", "pipeline_eri"]
            ]
            if not logger_config["handlers"]:
                logger_config["handlers"] = ["root"]

    def handler_filter_injection(filters: list):
        for _, handler in logging_dict["handlers"].items():
            handler.setdefault("filters", []).extend(filters)

    logging_dict.setdefault("filters", {}).update(
        {"bamboo_engine_node_info_filter": {"()": "bkflow.utils.logging.BambooEngineNodeInfoFilter"}}
    )
    handler_filter_injection(["bamboo_engine_node_info_filter"])

    # 日志中添加trace_id
    if env.ENABLE_OTEL_TRACE:
        trace_format = (
            "[trace_id]: %(otelTraceID)s [span_id]: %(otelSpanID)s [resource.service.name]: %(otelServiceName)s"
        )
    else:
        logging_dict.setdefault("filters", {}).update(
            {"trace_id_inject_filter": {"()": "bkflow.utils.logging.TraceIDInjectFilter"}}
        )
        handler_filter_injection(["trace_id_inject_filter"])
        trace_format = "[trace_id]: %(trace_id)s"
    inject_logging_trace_info(logging_dict, ("verbose",), trace_format)


# 初始化管理员列表，列表中的人员将拥有预发布环境和正式环境的管理员权限
# 注意：请在首次提测和上线前修改，之后的修改将不会生效
INIT_SUPERUSER = ["admin"]

# AJAX 请求弹窗续期登陆设置
IS_AJAX_PLAIN_MODE = True

TEMPLATES[0]["OPTIONS"]["context_processors"] += ("bkflow.interface.context_processors.bkflow_settings",)

PAGE_NOT_FOUND_URL_KEY = "page_not_found"
BLUEAPPS_SPECIFIC_REDIRECT_KEY = "page_not_found"

# 使用mako模板时，默认打开的过滤器：h(过滤html)
MAKO_DEFAULT_FILTERS = ["h"]

# BKUI是否使用了history模式
IS_BKUI_HISTORY_MODE = False

# 国际化配置
LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
LANGUAGE_CODE = "zh-hans"
LANGUAGE_COOKIE_NAME = "blueking_language"

LANGUAGES = (
    ("en", "English"),
    ("zh-hans", "简体中文"),
)

# OTEL配置
BK_APP_OTEL_INSTRUMENT_DB_API = True
INSTALLED_APPS += ("blueapps.opentelemetry.instrument_app",)

# 由于其他平台使用SDK对接时，可能需要访问内置插件的静态文件和依赖的接口，因此特殊开放这类接口允许跨域访问
INSTALLED_APPS += ("corsheaders",)
if "corsheaders.middleware.CorsMiddleware" not in MIDDLEWARE:
    MIDDLEWARE = ("corsheaders.middleware.CorsMiddleware",) + MIDDLEWARE
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "OPTIONS"]
# 允许 static、openapi 路径跨域访问
CORS_URLS_REGEX = r"^/(static\/components|openapi)/.*$"

"""
以下为框架代码 请勿修改
"""
# celery settings
if IS_USE_CELERY:
    INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    INSTALLED_APPS += ("django_celery_beat", "django_celery_results")
    CELERY_ENABLE_UTC = False
    CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"

# remove disabled apps
if locals().get("DISABLED_APPS"):
    INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    DISABLED_APPS = locals().get("DISABLED_APPS", [])

    INSTALLED_APPS = [_app for _app in INSTALLED_APPS if _app not in DISABLED_APPS]

    _keys = (
        "AUTHENTICATION_BACKENDS",
        "DATABASE_ROUTERS",
        "FILE_UPLOAD_HANDLERS",
        "MIDDLEWARE",
        "PASSWORD_HASHERS",
        "TEMPLATE_LOADERS",
        "STATICFILES_FINDERS",
        "TEMPLATE_CONTEXT_PROCESSORS",
    )

    import itertools

    for _app, _key in itertools.product(DISABLED_APPS, _keys):
        if locals().get(_key) is None:
            continue
        locals()[_key] = tuple([_item for _item in locals()[_key] if not _item.startswith(_app + ".")])
