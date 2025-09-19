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
from enum import Enum
from urllib.parse import urlparse

from blueapps.core.celery.celery import app
from celery.schedules import crontab
from django.core.serializers.json import DjangoJSONEncoder
from pydantic import BaseModel

import env
from bkflow.task.celery.settings import get_task_queues
from bkflow.utils.dates import json_encoder_default
from config import APP_CODE
from config.default import (  # noqa; noqa、
    AUTHENTICATION_BACKENDS,
    BASE_DIR,
    BK_SAAS_HOSTS,
    BKSAAS_DEFAULT_MODULE_NAME,
    INSTALLED_APPS,
    MIDDLEWARE,
)


class BKFLOWModuleType(str, Enum):
    """模块类型"""

    interface = "interface"
    engine = "engine"


class BKFLOWResourceIsolationLevel(str, Enum):
    """模块资源隔离级别"""

    only_calculation = "only_calculation"
    all_resource = "all_resource"


class BKFLOWDatabaseConfig(BaseModel):
    """模块数据库配置"""

    engine: str = "django.db.backends.mysql"
    name: str
    user: str
    password: str = ""
    host: str
    port: str

    @classmethod
    def get_database_config(cls):
        return cls(
            engine=env.BKFLOW_DATABASE_ENGINE,
            name=env.BKFLOW_DATABASE_NAME,
            user=env.BKFLOW_DATABASE_USER,
            password=env.BKFLOW_DATABASE_PASSWORD,
            host=env.BKFLOW_DATABASE_HOST,
            port=env.BKFLOW_DATABASE_PORT,
        )


class BKFLOWModule(BaseModel):
    """模块配置"""

    broker_url: str = ""
    code: str = None
    type: BKFLOWModuleType
    isolation_level: BKFLOWResourceIsolationLevel = None

    @classmethod
    def get_module(cls):
        return cls(
            type=env.BKFLOW_MODULE_TYPE,
            code=env.BKFLOW_MODULE_CODE,
            isolation_level=env.BKFLOW_RESOURCE_ISOLATION_LEVEL,
            broker_url=env.BKFLOW_CELERY_BROKER_URL,
        )


def check_engine_admin_permission(request, *args, **kwargs):
    from django.conf import settings  # noqa

    if (
        request.user.is_superuser
        or (request.app_internal_token and request.app_internal_token == settings.APP_INTERNAL_TOKEN)
        or settings.APP_INTERNAL_VALIDATION_SKIP
    ):
        return True
    return False


BKFLOW_MODULE = BKFLOWModule.get_module()

if env.BKFLOW_MODULE_TYPE == BKFLOWModuleType.engine.value:

    if BKFLOW_MODULE.broker_url:
        BROKER_URL = env.BKFLOW_CELERY_BROKER_URL

    if BKFLOW_MODULE.isolation_level == BKFLOWResourceIsolationLevel.all_resource.value:
        db_config = BKFLOWDatabaseConfig.get_database_config()
        DATABASES = {
            "default": {
                "ENGINE": db_config.engine,
                "NAME": db_config.name,
                "USER": db_config.user,
                "PASSWORD": db_config.password,
                "HOST": db_config.host,
                "PORT": db_config.port,
            },
        }

    from pipeline.celery.settings import CELERY_QUEUES, CELERY_ROUTES  # noqa
    from pipeline.eri.celery import queues as eri_queues  # noqa

    CELERY_QUEUES.extend(eri_queues.QueueResolver(BKFLOW_MODULE.code).queues())
    CELERY_QUEUES.extend(get_task_queues(BKFLOW_MODULE.code))

    PIPELINE_ENGINE_ADMIN_API_PERMISSION = "module_settings.check_engine_admin_permission"

    BKAPP_API_PLUGIN_REQUEST_TIMEOUT = env.BKAPP_API_PLUGIN_REQUEST_TIMEOUT

    INSTALLED_APPS += (
        "rest_framework",
        "drf_yasg",
        "pipeline",
        "pipeline.component_framework",
        "pipeline.variable_framework",
        "pipeline.engine",
        "pipeline.eri",
        "pipeline.log",
        "pipeline.contrib.engine_admin",
        "pipeline.contrib.periodic_task",
        "pipeline.django_signal_valve",
        "bkflow.task",
        "django_extensions",
        "bkflow.pipeline_plugins",
        "plugin_service",
        "bkflow.contrib.operation_record",
        "django_dbconn_retry",
        "bkflow.contrib.expired_cleaner",
    )

    BKFLOW_CELERY_ROUTES = {
        "bkflow.contrib.expired_cleaner.tasks.clean_task": {
            "queue": f"clean_task_{BKFLOW_MODULE.code}",
            "routing_key": f"clean_task_{BKFLOW_MODULE.code}",
        }
    }
    CELERY_ROUTES.update(BKFLOW_CELERY_ROUTES)

    app.conf.beat_schedule = {
        "expired_task_cleaning": {
            "task": "bkflow.contrib.expired_cleaner.tasks.clean_task",
            "schedule": crontab(env.CLEAN_TASK_CRONTAB),
        },
    }

    MIDDLEWARE += ("bkflow.permission.middleware.TokenMiddleware",)

    REST_FRAMEWORK = {
        "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
        "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
    }

    DjangoJSONEncoder.default = json_encoder_default
    json.JSONEncoder = DjangoJSONEncoder

    # Redis 过期时间节点池 KEY
    EXECUTING_NODE_POOL = f"bkflow_engine_executing_node_pool_{BKFLOW_MODULE.code}"

    if env.BKAPP_REDIS_HOST:
        REDIS = {
            "host": env.BKAPP_REDIS_HOST,
            "port": env.BKAPP_REDIS_PORT,
            "password": env.BKAPP_REDIS_PASSWORD,
            "service_name": env.BKAPP_REDIS_SERVICE_NAME,
            "mode": env.BKAPP_REDIS_MODE,
            "db": env.BKAPP_REDIS_DB,
            "sentinel_password": env.BKAPP_REDIS_SENTINEL_PASSWORD,
        }

    INTERFACE_APP_INTERNAL_TOKEN = env.INTERFACE_APP_INTERNAL_TOKEN
    INTERFACE_APP_URL = (
        env.INTERFACE_APP_URL or BK_SAAS_HOSTS.get(APP_CODE, {}).get(BKSAAS_DEFAULT_MODULE_NAME, "")
    ).rstrip("/")
    NODE_LOG_DATA_SOURCE = env.NODE_LOG_DATA_SOURCE
    NODE_LOG_DATA_SOURCE_CONFIG = env.NODE_LOG_DATA_SOURCE_CONFIG
    PAASV3_APIGW_API_TOKEN = env.PAASV3_APIGW_API_TOKEN
    LOG_PERSISTENT_DAYS = env.LOG_PERSISTENT_DAYS
    USE_BKFLOW_CREDENTIAL = env.USE_BKFLOW_CREDENTIAL
    CLEAN_TASK_BATCH_NUM = env.CLEAN_TASK_BATCH_NUM
    CLEAN_TASK_NODE_BATCH_NUM = env.CLEAN_TASK_NODE_BATCH_NUM
    CLEAN_TASK_EXPIRED_DAYS = env.CLEAN_TASK_EXPIRED_DAYS
    ENABLE_CLEAN_TASK = env.ENABLE_CLEAN_TASK
    CLEAN_TASK_CRONTAB = env.CLEAN_TASK_CRONTAB

elif env.BKFLOW_MODULE_TYPE == BKFLOWModuleType.interface.value:

    INSTALLED_APPS += (
        "rest_framework",
        "drf_yasg",
        "pipeline",
        "pipeline.component_framework",
        "pipeline.variable_framework",
        "pipeline.engine",
        "pipeline.eri",
        "pipeline.log",
        "pipeline.contrib.periodic_task",
        "pipeline.django_signal_valve",
        "bkflow.template",
        "bkflow.permission",
        "bkflow.space",
        "bkflow.apigw",
        "bkflow.plugin",
        "bkflow.interface",
        "bkflow.decision_table",
        "apigw_manager.apigw",
        "bkflow.pipeline_plugins",
        "bkflow.admin",
        "plugin_service",
        "bkflow.contrib.operation_record",
        "django_dbconn_retry",
        "webhook",
        "version_log",
        "bk_notice_sdk",
        "bkflow.bk_plugin",
        "bkflow.pipeline_web",
    )

    VARIABLE_KEY_BLACKLIST = (
        env.VARIABLE_KEY_BLACKLIST.strip().strip(",").split(",") if env.VARIABLE_KEY_BLACKLIST else []
    )
    MIDDLEWARE += (
        "whitenoise.middleware.WhiteNoiseMiddleware",  # Here
        "bkflow.permission.middleware.TokenMiddleware",
        "apigw_manager.apigw.authentication.ApiGatewayJWTGenericMiddleware",  # JWT 认证
        "apigw_manager.apigw.authentication.ApiGatewayJWTAppMiddleware",  # JWT 透传的应用信息
        "apigw_manager.apigw.authentication.ApiGatewayJWTUserMiddleware",  # JWT 透传的用户信息
    )  # noqa

    # 添加自定义的
    AUTHENTICATION_BACKENDS += ("bkflow.interface.utils.APIGWUserModelBackend",)
    BK_APIGW_NAME = env.BK_APIGW_NAME
    BK_API_URL_TMPL = env.BK_APIGW_URL_TMPL
    CALLBACK_KEY = env.CALLBACK_KEY
    STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
    BK_APIGW_REQUIRE_EXEMPT = env.BK_APIGW_REQUIRE_EXEMPT

    BK_APIGW_MANAGER_MAINTAINERS = env.BK_APIGW_MANAGER_MAINTAINERS
    api_host = urlparse(env.BKAPP_APIGW_API_HOST or BK_SAAS_HOSTS.get(APP_CODE, {}).get(BKSAAS_DEFAULT_MODULE_NAME, ""))
    BK_APIGW_API_SERVER_HOST = api_host.netloc
    BK_APIGW_API_SERVER_SUB_PATH = api_host.path.lstrip("/")
    BK_APIGW_RESOURCE_DOCS_ARCHIVE_FILE = os.path.join(BASE_DIR, "bkflow", "apigw", "docs", "apigw-docs.zip")
    BK_APIGW_GRANT_APPS = env.BK_APIGW_GRANT_APPS

    # version log config
    VERSION_LOG = {"FILE_TIME_FORMAT": "%Y-%m-%d", "LANGUAGE_MAPPINGS": {"en": "en"}}

    # bk notice config
    DISABLE_REGISTER_BKFLOW_TO_BKNOTICE = env.DISABLE_REGISTER_BKFLOW_TO_BKNOTICE

    # ban 掉 admin 权限
    BLOCK_ADMIN_PERMISSION = env.BLOCK_ADMIN_PERMISSION

    # 添加定时任务
    app.conf.beat_schedule = {
        # 同步蓝鲸插件任务
        "sync_bk_plugins": {
            "task": "bkflow.bk_plugin.tasks.sync_bk_plugins",
            "schedule": crontab(env.SYNC_BK_PLUGINS_CRONTAB),
        }
    }
