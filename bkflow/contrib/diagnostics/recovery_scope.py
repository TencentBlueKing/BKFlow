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

from django.conf import settings

from bkflow.task.models import TaskInstance


def _configured_scopes():
    """返回标准化后的自动重放空间白名单。"""
    raw = getattr(settings, "DIAGNOSTICS_RECOVERY_SCOPES", ())
    items = raw.split(",") if isinstance(raw, str) else raw
    return {str(item).strip() for item in items or () if str(item).strip()}


def in_recovery_scope(root_pipeline_id):
    """仅允许白名单内且仍有效的任务进入自动重放范围。"""
    scopes = _configured_scopes()
    if not scopes:
        return False

    task_scope = (
        TaskInstance.objects.filter(
            instance_id=root_pipeline_id,
            is_deleted=False,
            is_expired=False,
        )
        .values("space_id", "tenant_id")
        .first()
    )
    if task_scope is None:
        return False

    space_id = str(task_scope["space_id"])
    tenant_space_id = "{}:{}".format(task_scope["tenant_id"], space_id)
    if settings.ENABLE_MULTI_TENANT_MODE:
        return tenant_space_id in scopes
    return space_id in scopes or tenant_space_id in scopes
