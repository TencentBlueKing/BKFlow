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

from django.test import override_settings

from bkflow.contrib.diagnostics import recovery_scope


def _resolve(mocker, task_scope, root_pipeline_id="root"):
    task_model = mocker.patch.object(recovery_scope, "TaskInstance")
    task_model.objects.filter.return_value.values.return_value.first.return_value = task_scope
    return recovery_scope.in_recovery_scope(root_pipeline_id), task_model


@override_settings(DIAGNOSTICS_RECOVERY_SCOPES=(), ENABLE_MULTI_TENANT_MODE=False)
def test_empty_scope_list_denies_auto_replay(mocker):
    """空白名单必须拒绝自动重放。"""
    allowed, task_model = _resolve(mocker, {"space_id": 1, "tenant_id": "default"})

    assert allowed is False
    task_model.objects.filter.assert_not_called()


@override_settings(DIAGNOSTICS_RECOVERY_SCOPES=("2",), ENABLE_MULTI_TENANT_MODE=False)
def test_single_tenant_scope_matches_space_id(mocker):
    """单租户按空间 ID 判断自动重放范围。"""
    allowed, task_model = _resolve(mocker, {"space_id": 2, "tenant_id": "default"})

    assert allowed is True
    task_model.objects.filter.assert_called_once_with(
        instance_id="root",
        is_deleted=False,
        is_expired=False,
    )
    task_model.objects.filter.return_value.values.assert_called_once_with("space_id", "tenant_id")


@override_settings(DIAGNOSTICS_RECOVERY_SCOPES="tenant-a:2", ENABLE_MULTI_TENANT_MODE=True)
def test_multi_tenant_scope_requires_tenant_and_space(mocker):
    """多租户必须同时匹配租户和空间，不能只凭空间 ID 放行。"""
    allowed, _task_model = _resolve(mocker, {"space_id": 2, "tenant_id": "tenant-a"})
    denied, _task_model = _resolve(mocker, {"space_id": 2, "tenant_id": "tenant-b"})

    assert allowed is True
    assert denied is False


@override_settings(DIAGNOSTICS_RECOVERY_SCOPES=("tenant-a:2",), ENABLE_MULTI_TENANT_MODE=False)
def test_single_tenant_accepts_explicit_tenant_scope(mocker):
    """单租户也接受显式租户空间写法，便于部署模式切换。"""
    allowed, _task_model = _resolve(mocker, {"space_id": 2, "tenant_id": "tenant-a"})

    assert allowed is True


@override_settings(DIAGNOSTICS_RECOVERY_SCOPES=("1",), ENABLE_MULTI_TENANT_MODE=False)
def test_unknown_or_inactive_root_is_denied(mocker):
    """查不到任务或任务已删除、过期时必须拒绝自动重放。"""
    allowed, task_model = _resolve(mocker, None, root_pipeline_id="missing-root")

    assert allowed is False
    task_model.objects.filter.assert_called_once_with(
        instance_id="missing-root",
        is_deleted=False,
        is_expired=False,
    )
