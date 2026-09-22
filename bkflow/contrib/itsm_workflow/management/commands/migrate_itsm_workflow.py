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

import os
from io import BytesIO

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bkflow.utils.platform import use_apigw
from packages.bkapi.bk_itsm4.shortcuts import get_client_by_username


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-t", "--tenant_id", help="租户ID", type=str, required=True)

    def handle(self, *args, **options):
        tenant_id = (options.get("tenant_id") or "").strip()
        if not tenant_id:
            raise CommandError("必须指定非空 tenant_id")
        if not use_apigw():
            raise CommandError("Legacy platform mode does not initialize ITSM4 tenants")
        if not settings.ENABLE_MULTI_TENANT_MODE and tenant_id != "default":
            raise CommandError("Single-tenant mode only initializes the default tenant")
        client = get_client_by_username("bk_admin", stage=settings.BK_APIGW_STAGE_NAME)
        template_path = os.path.join(
            settings.BASE_DIR, "bkflow/contrib/itsm_workflow/template/itsm_migrate_template.json"
        )
        try:
            # 先验证本地模板，再产生外部写入。
            with open(template_path, encoding="utf-8") as template_file:
                tenant_template = template_file.read().replace("__tenant_id__", tenant_id)
            result = client.api.system_create(
                {"name": settings.APP_CODE, "code": settings.APP_CODE, "token": settings.SECRET_KEY},
                headers={"X-Bk-Tenant-Id": tenant_id},
            )
            self._check_result("注册 ITSM 系统", result)
            with BytesIO(tenant_template.encode("utf-8")) as file_obj:
                result = client.api.system_migrate(headers={"X-Bk-Tenant-Id": tenant_id}, files={"file": file_obj})
            self._check_result("导入 ITSM 工作流", result)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"租户 {tenant_id} 初始化失败，请检查 ITSM 服务和模板") from exc

    @staticmethod
    def _check_result(operation, result):
        """业务失败和传输失败均使命令返回非零退出码。"""
        if not isinstance(result, dict) or result.get("result") is not True:
            message = result.get("message", "响应无成功标志") if isinstance(result, dict) else "响应为空或格式错误"
            raise CommandError(f"{operation}失败: {message}")
