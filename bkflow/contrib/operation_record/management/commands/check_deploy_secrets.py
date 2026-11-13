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

from cryptography.fernet import Fernet
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, router

import env
from module_settings import BKFLOWModuleType

# ModuleInfo.token 的字段长度；默认引擎 token 需要存入该字段，并与 default-engine 的 APP_INTERNAL_TOKEN 一致。
MODULE_TOKEN_MAX_LENGTH = 32
GUIDE_PATH = "docs/guide/security_hardening_upgrade.md"


def _is_valid_fernet_key(key: bytes) -> bool:
    """回调链接使用 Fernet 加密，空值或格式错误都会导致节点无法生成回调地址。"""
    if not key:
        return False
    try:
        Fernet(key)
    except (TypeError, ValueError):
        return False
    return True


class Command(BaseCommand):
    help = "发布前检查模块间调用 token 和回调密钥是否已注入，只输出配置项名称不输出取值"

    def handle(self, *args, **options):
        if settings.RUN_MODE == "DEVELOP":
            self.stdout.write("RUN_MODE=DEVELOP, skip deploy secret check")
            return

        problems = []
        app_internal_token = settings.APP_INTERNAL_TOKEN or ""
        if not app_internal_token:
            problems.append("APP_INTERNAL_TOKEN(未配置)")
        if not _is_valid_fernet_key(env.CALLBACK_KEY):
            problems.append("BKFLOW_DEFAULT_CALLBACK_KEY(未配置或不是有效的 Fernet 密钥)")

        if env.BKFLOW_MODULE_TYPE == BKFLOWModuleType.engine.value:
            if len(app_internal_token) > MODULE_TOKEN_MAX_LENGTH:
                problems.append(f"APP_INTERNAL_TOKEN(超过{MODULE_TOKEN_MAX_LENGTH}个字符，无法登记到模块信息)")
            if not env.INTERFACE_APP_INTERNAL_TOKEN:
                problems.append("INTERFACE_APP_INTERNAL_TOKEN(未配置)")
        elif env.BKFLOW_MODULE_TYPE == BKFLOWModuleType.interface.value:
            problems.extend(self._check_default_engine_module())

        if problems:
            raise CommandError(f"部署密钥检查未通过: {', '.join(problems)}。请按 {GUIDE_PATH} 注入后重新发布")
        self.stdout.write("deploy secret check passed")

    def _check_default_engine_module(self):
        """存量默认引擎记录保持不变；只有首次登记时才要求通过环境变量提供 token 和入口。"""
        env_token = os.getenv("DEFAULT_ENGINE_APP_INTERNAL_TOKEN", "")
        stored_token = self._get_stored_default_engine_token()
        if stored_token:
            if env_token and env_token != stored_token:
                self.stderr.write(
                    "DEFAULT_ENGINE_APP_INTERNAL_TOKEN 与已登记的默认引擎 token 不一致；sync_default_module 不会覆盖存量记录，"
                    "如需轮换请同时更新 ModuleInfo(space_id=0).token 和 default-engine 的 APP_INTERNAL_TOKEN"
                )
            return []

        problems = []
        if not env_token:
            problems.append("DEFAULT_ENGINE_APP_INTERNAL_TOKEN(未配置，且尚未登记默认引擎模块)")
        elif len(env_token) > MODULE_TOKEN_MAX_LENGTH:
            problems.append(f"DEFAULT_ENGINE_APP_INTERNAL_TOKEN(超过{MODULE_TOKEN_MAX_LENGTH}个字符)")
        if not settings.BKAPP_DEFAULT_ENGINE_MODULE_ENTRY:
            problems.append("BKAPP_DEFAULT_ENGINE_MODULE_ENTRY(未配置，且尚未登记默认引擎模块)")
        return problems

    @staticmethod
    def _get_stored_default_engine_token():
        """发布前检查早于迁移，全新数据库尚无模块信息表时按未登记处理。"""
        module_info_model = apps.get_model("bkflow_admin", "ModuleInfo")
        connection = connections[router.db_for_read(module_info_model)]
        if module_info_model._meta.db_table not in connection.introspection.table_names():
            return ""
        return module_info_model.objects.filter(space_id=0).values_list("token", flat=True).first() or ""
