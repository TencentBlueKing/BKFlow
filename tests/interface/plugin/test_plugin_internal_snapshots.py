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

from unittest.mock import patch

import pytest
from blueapps.account.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.plugin.models import OpenPluginCatalogIndex, SpaceOpenPluginAvailability
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService
from bkflow.plugin.services.open_plugin_snapshot import OpenPluginSnapshotService
from bkflow.plugin.views.internal import PluginInternalViewSet
from bkflow.space.models import Space


def build_open_plugin_pipeline_tree(plugin_version="1.2.0"):
    return {
        "activities": {
            "node1": {
                "id": "node1",
                "type": "ServiceActivity",
                "component": {
                    "code": "uniform_api",
                    "version": "v4.0.0",
                    "api_meta": {"source_key": "sops"},
                    "data": {
                        "uniform_api_plugin_id": {"value": "open_plugin_001"},
                        "uniform_api_plugin_version": {"value": plugin_version},
                    },
                },
            }
        }
    }


def create_catalog(space_id, enabled=True, versions=None):
    OpenPluginCatalogIndex.objects.create(
        space_id=space_id,
        source_key="sops",
        plugin_id="open_plugin_001",
        plugin_code="job_execute_task",
        plugin_name="JOB 执行作业",
        plugin_source="builtin",
        group_name="作业平台",
        wrapper_version="v4.0.0",
        default_version="1.2.0",
        latest_version="9.9.9",
        versions=versions or ["1.2.0"],
        meta_url_template="https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
        status=OpenPluginCatalogIndex.Status.AVAILABLE,
    )
    SpaceOpenPluginAvailability.objects.create(
        space_id=space_id,
        source_key="sops",
        plugin_id="open_plugin_001",
        enabled=enabled,
    )


def call_build_snapshots(user, payload):
    factory = APIRequestFactory()
    view = PluginInternalViewSet.as_view({"post": "build_open_plugin_snapshots"})
    request = factory.post("/api/plugin/internal/build_open_plugin_snapshots/", payload, format="json")
    force_authenticate(request, user=user)
    return view(request)


@pytest.mark.django_db
@patch("bkflow.plugin.services.open_plugin_snapshot.OpenPluginSnapshotService.build_schema_snapshot")
def test_build_open_plugin_snapshots_prepare_returns_both_snapshots(mock_build_schema):
    """prepare 模式校验通过后返回引用快照和 schema 快照。"""
    user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    space = Space.objects.create(name="snap-space", app_code="test")
    create_catalog(space.id, enabled=True)
    OpenPluginGrantService.grant(space_id=space.id, source_key="sops", operator="admin")
    mock_build_schema.return_value = {
        "node1": {
            "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
            "plugin_id": "open_plugin_001",
            "plugin_code": "job_execute_task",
            "inputs": [{"name": "bk_biz_id"}],
            "outputs": [],
            "description": "job",
        }
    }

    response = call_build_snapshots(
        user,
        {
            "space_id": space.id,
            "pipeline_tree": build_open_plugin_pipeline_tree(),
            "username": "admin",
            "scope_type": "biz",
            "scope_value": "2",
            "mode": "prepare",
        },
    )

    assert response.data["result"] is True
    data = response.data["data"]
    assert data["reference_snapshot"][0]["plugin_id"] == "open_plugin_001"
    assert data["schema_snapshot"]["node1"]["inputs"] == [{"name": "bk_biz_id"}]
    assert data["changed"] is True
    assert "extra_info" not in data


@pytest.mark.django_db
def test_build_open_plugin_snapshots_prepare_rejects_ungranted():
    """prepare 模式必须拦截未准入来源，不能只扫 tree。"""
    user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    space = Space.objects.create(name="snap-space", app_code="test")
    create_catalog(space.id, enabled=True)

    response = call_build_snapshots(
        user,
        {
            "space_id": space.id,
            "pipeline_tree": build_open_plugin_pipeline_tree(),
            "mode": "prepare",
        },
    )

    assert response.data["result"] is False
    assert "来源" in response.data["message"]


@pytest.mark.django_db
@patch("bkflow.plugin.services.open_plugin_snapshot.OpenPluginSnapshotService.build_schema_snapshot")
def test_build_open_plugin_snapshots_backfill_keeps_existing_schema(mock_build_schema):
    """backfill 不覆盖已有非空 schema 快照。"""
    user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    space = Space.objects.create(name="snap-space", app_code="test")
    create_catalog(space.id, enabled=True)
    OpenPluginGrantService.grant(space_id=space.id, source_key="sops", operator="admin")
    extra_info = {
        "plugin_reference_snapshot": [
            {
                "node_id": "node1",
                "plugin_id": "open_plugin_001",
                "source_key": "sops",
                "plugin_version": "1.2.0",
                "wrapper_version": "v4.0.0",
            }
        ],
        "plugin_schema_snapshot": {
            "node1": {
                "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
                "plugin_id": "open_plugin_001",
                "description": "keep-me",
            }
        },
        "custom_context": {"credentials": {"gw": {"bk_app_secret": "SECRET_TOKEN"}}},
    }

    response = call_build_snapshots(
        user,
        {
            "space_id": space.id,
            "pipeline_tree": build_open_plugin_pipeline_tree(),
            "plugin_reference_snapshot": extra_info["plugin_reference_snapshot"],
            "plugin_schema_snapshot": extra_info["plugin_schema_snapshot"],
            "extra_info": extra_info,
            "mode": "backfill",
        },
    )

    assert response.data["result"] is True
    assert response.data["data"]["changed"] is False
    assert response.data["data"]["schema_snapshot"]["node1"]["description"] == "keep-me"
    assert "extra_info" not in response.data["data"]
    assert "SECRET_TOKEN" not in str(response.data)
    mock_build_schema.assert_not_called()


@pytest.mark.django_db
@patch("bkflow.plugin.services.open_plugin_snapshot.OpenPluginSnapshotService.build_schema_snapshot")
def test_build_open_plugin_snapshots_backfill_fails_when_exact_version_missing(mock_build_schema):
    """历史精确版本无法获取时，backfill 必须失败，不得用最新 schema 冒充。"""
    user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    space = Space.objects.create(name="snap-space", app_code="test")
    create_catalog(space.id, enabled=True, versions=["9.9.9"])
    OpenPluginGrantService.grant(space_id=space.id, source_key="sops", operator="admin")
    mock_build_schema.side_effect = ValueError("开放插件 [open_plugin_001] 版本 [1.2.0] 当前不可用")

    response = call_build_snapshots(
        user,
        {
            "space_id": space.id,
            "pipeline_tree": build_open_plugin_pipeline_tree(plugin_version="1.2.0"),
            "extra_info": {},
            "mode": "backfill",
        },
    )

    assert response.data["result"] is False
    assert "1.2.0" in response.data["message"]
    assert "SECRET_TOKEN" not in str(response.data)


@pytest.mark.django_db
@patch("bkflow.plugin.services.open_plugin_snapshot.OpenPluginSnapshotService.build_schema_snapshot")
def test_build_open_plugin_snapshots_ignores_request_extra_info(mock_build_schema):
    """即使请求误带 extra_info，接口也不得回传或依赖其中的凭证字段。"""
    user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
    space = Space.objects.create(name="snap-space", app_code="test")
    create_catalog(space.id, enabled=True)
    OpenPluginGrantService.grant(space_id=space.id, source_key="sops", operator="admin")
    mock_build_schema.return_value = {
        "node1": {
            "schema_protocol_version": OpenPluginSnapshotService.SCHEMA_PROTOCOL_VERSION,
            "plugin_id": "open_plugin_001",
            "inputs": [],
            "outputs": [],
        }
    }

    response = call_build_snapshots(
        user,
        {
            "space_id": space.id,
            "pipeline_tree": build_open_plugin_pipeline_tree(),
            "mode": "prepare",
            "extra_info": {"custom_context": {"credentials": {"gw": {"bk_app_secret": "SECRET_TOKEN"}}}},
        },
    )

    assert response.data["result"] is True
    assert "extra_info" not in response.data["data"]
    assert "SECRET_TOKEN" not in str(response.data)
    assert "bk_app_secret" not in str(response.data)
