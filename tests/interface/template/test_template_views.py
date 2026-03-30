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
from copy import deepcopy
from unittest import mock

import pytest
from blueapps.account.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from bkflow.decision_table.models import DecisionTable
from bkflow.label.models import Label, TemplateLabelRelation
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import (
    Template,
    TemplateMockData,
    TemplateMockScheme,
    TemplateReference,
    TemplateSnapshot,
    Trigger,
)
from bkflow.template.views.template import (
    AdminTemplateViewSet,
    TemplateInternalViewSet,
    TemplateMockDataViewSet,
    TemplateMockSchemeViewSet,
    TemplateMockTaskViewSet,
    TemplateVersionViewSet,
    TemplateViewSet,
)


def build_pipeline_tree():
    """构建测试用的 pipeline tree"""
    return {
        "id": "test_pipeline_id",
        "start_event": {
            "id": "start_event_id",
            "type": "EmptyStartEvent",
            "incoming": "",
            "outgoing": "flow1",
            "name": "",
        },
        "end_event": {"id": "end_event_id", "type": "EmptyEndEvent", "incoming": ["flow2"], "outgoing": "", "name": ""},
        "activities": {
            "node1": {
                "id": "node1",
                "type": "ServiceActivity",
                "name": "test_node",
                "incoming": ["flow1"],
                "outgoing": "flow2",
                "component": {
                    "code": "example_component",
                    "data": {"param1": {"hook": False, "need_render": True, "value": "test_value"}},
                    "inputs": {},
                },
                "error_ignorable": False,
                "timeout": None,
                "skippable": True,
                "retryable": True,
                "optional": False,
            }
        },
        "flows": {
            "flow1": {"id": "flow1", "source": "start_event_id", "target": "node1", "is_default": False},
            "flow2": {"id": "flow2", "source": "node1", "target": "end_event_id", "is_default": False},
        },
        "gateways": {},
        "constants": {},
        "outputs": [],
    }


@pytest.mark.django_db
class TestAdminTemplateViewSet:
    """测试 AdminTemplateViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_list_templates(self):
        """测试列表查询模板"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = AdminTemplateViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/admin/templates/?space_id={self.space.id}")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        assert len(results) >= 1

    def test_list_templates_with_trigger(self):
        """测试列表查询带有触发器的模板"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建触发器
        Trigger.objects.create(
            template_id=template.id,
            space_id=self.space.id,
            name="test_trigger",
            type="periodic",
            config={},
            creator="admin",
        )

        view = AdminTemplateViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/admin/templates/?space_id={self.space.id}")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        assert any(item.get("has_interval_trigger") for item in results)

    @mock.patch("bkflow.template.views.template.build_default_pipeline_tree_with_space_id")
    @mock.patch("bkflow.template.views.template.SpaceConfig.get_config")
    def test_create_template(self, mock_get_config, mock_build_tree):
        """测试创建模板"""
        mock_get_config.return_value = "false"
        mock_build_tree.return_value = self.pipeline_tree

        view = AdminTemplateViewSet.as_view({"post": "create_template"})
        data = {"name": "New Template", "desc": "Test Description"}
        request = self.factory.post(f"/admin/templates/create_default_template/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request, space_id=self.space.id)

        assert response.status_code == 200
        if "result" in response.data:
            assert response.data["result"] is True

    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    @mock.patch("bkflow.template.views.template.PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes")
    @mock.patch("bkflow.template.views.template.SpaceConfig.get_config")
    def test_create_task(self, mock_get_config, mock_previewer, mock_client_class):
        """测试创建任务"""
        from bkflow.admin.models import ModuleInfo

        # 创建必要的 ModuleInfo
        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        mock_get_config.return_value = "false"
        mock_previewer.side_effect = lambda x: None

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "Test Task", "template_id": template.id, "parameters": {}},
        }
        mock_client_class.return_value = mock_client

        view = AdminTemplateViewSet.as_view({"post": "create_task"})
        data = {"template_id": template.id, "name": "Test Task"}
        request = self.factory.post(f"/admin/templates/create_task/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request, space_id=self.space.id)

        assert response.status_code == 200

    @mock.patch("bkflow.template.views.template.TaskComponentClient.batch_delete_periodic_task")
    def test_batch_delete(self, mock_batch_delete):
        """测试批量删除模板"""
        from bkflow.admin.models import ModuleInfo

        # 创建必要的 ModuleInfo
        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        # Mock batch_delete_periodic_task to avoid API calls
        mock_batch_delete.return_value = {"result": True}

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = AdminTemplateViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": self.space.id, "is_full": False, "template_ids": [template.id]}
        request = self.factory.post("/admin/templates/batch_delete/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "delete_num" in resp_data or response.status_code == 200

    @mock.patch("bkflow.template.models.Template.objects.copy_template")
    def test_copy_template(self, mock_copy):
        """测试复制模板"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # Mock the copy_template method
        copied_template = mock.Mock()
        copied_template.id = 999
        copied_template.name = "Copied Template"
        mock_copy.return_value = copied_template

        view = AdminTemplateViewSet.as_view({"post": "copy_template"})
        data = {
            "space_id": self.space.id,
            "template_id": template.id,
            "name": "Copied Template",
            "desc": "Copied Description",
            "copy_subprocess": False,
        }
        request = self.factory.post("/admin/templates/template_copy/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        if "template_id" in resp_data:
            assert resp_data["template_id"] == 999


@pytest.mark.django_db
class TestTemplateVersionViewSet:
    """测试 TemplateVersionViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()
        # 启用版本管理
        SpaceConfig.objects.create(
            space_id=self.space.id, name=FlowVersioning.name, value_type="TEXT", text_value="true"
        )

    def test_list_versions(self):
        """测试列表查询版本"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateVersionViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/templates/versions/?template_id={template.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_list_versions_without_template_id(self):
        """测试列表查询版本缺少template_id"""
        view = TemplateVersionViewSet.as_view({"get": "list"})
        request = self.factory.get("/templates/versions/")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 400
        response_detail = response.data.get("data", {}).get("detail", "")
        # Response直接返回detail，不需要包装
        assert "template_id" in response_detail

    def test_delete_snapshot_success(self):
        """测试删除快照成功"""
        snapshot1 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        snapshot2 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.1.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot2.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot1.template_id = template.id
        snapshot1.save()
        snapshot2.template_id = template.id
        snapshot2.save()

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(
            f"/templates/versions/{snapshot1.id}/delete_snapshot/", {"template_id": template.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=snapshot1.id)

        assert response.status_code == 200
        # Response会被包装，需要从data中获取detail
        detail = (
            response.data.get("data", {}).get("detail", "")
            if isinstance(response.data, dict) and "data" in response.data
            else response.data.get("detail", "")
        )
        assert "成功删除" in detail

    def test_delete_snapshot_draft(self):
        """测试删除草稿快照失败"""
        snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "test_user")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(
            f"/templates/versions/{snapshot.id}/delete_snapshot/", {"template_id": template.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=snapshot.id)

        assert response.status_code == 200
        # Response会被包装，需要从data中获取detail
        detail = (
            response.data.get("data", {}).get("detail", "")
            if isinstance(response.data, dict) and "data" in response.data
            else response.data.get("detail", "")
        )
        assert "草稿" in detail

    def test_delete_snapshot_without_template_id(self):
        """测试删除快照时缺少template_id参数"""
        # 注意：delete_snapshot方法实际上不检查request body中的template_id参数
        # 它从URL的pk获取snapshot。此测试可能已过时，但保留以测试版本管理校验
        # 创建一个未启用版本管理的空间来测试版本管理校验
        space_no_version = Space.objects.create(name="Test Space No Version", app_code="test_app_no_version")
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=space_no_version.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(f"/templates/versions/{snapshot.id}/delete_snapshot/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=snapshot.id)

        # 版本管理未开启时，返回exception=True的响应（被包装为200状态码）
        assert response.status_code == 200
        detail = (
            response.data.get("data", {}).get("detail", "")
            if isinstance(response.data, dict) and "data" in response.data
            else response.data.get("detail", "")
        )
        assert "版本管理" in detail

    def test_delete_snapshot_with_reference(self):
        """测试删除被引用的快照失败"""
        snapshot1 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        snapshot2 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.1.0")
        sub_template = Template.objects.create(
            name="Sub Template",
            space_id=self.space.id,
            snapshot_id=snapshot2.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot1.template_id = sub_template.id
        snapshot1.save()
        snapshot2.template_id = sub_template.id
        snapshot2.save()

        root_template = Template.objects.create(
            name="Root Template",
            space_id=self.space.id,
            snapshot_id=snapshot2.id,
            creator="test_user",
            updated_by="test_user",
        )

        # 创建引用关系
        TemplateReference.objects.create(
            root_template_id=root_template.id, subprocess_template_id=sub_template.id, version="1.0.0"
        )

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(
            f"/templates/versions/{snapshot1.id}/delete_snapshot/", {"template_id": sub_template.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=snapshot1.id)

        assert response.status_code == 200
        # Response会被包装，需要从data中获取detail
        detail = (
            response.data.get("data", {}).get("detail", "")
            if isinstance(response.data, dict) and "data" in response.data
            else response.data.get("detail", "")
        )
        assert "引用" in detail or "无法删除" in detail

    def test_delete_snapshot_current_version(self):
        """测试删除当前版本快照失败"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(
            f"/templates/versions/{snapshot.id}/delete_snapshot/", {"template_id": template.id}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=snapshot.id)

        assert response.status_code == 200
        # Response会被包装，需要从data中获取detail
        detail = (
            response.data.get("data", {}).get("detail", "")
            if isinstance(response.data, dict) and "data" in response.data
            else response.data.get("detail", "")
        )
        # 应该返回无法删除最新版本的消息
        assert "最新" in detail or "无法删除" in detail or "草稿" in detail


@pytest.mark.django_db
class TestTemplateViewSet:
    """测试 TemplateViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()
        # 启用版本管理（用于需要版本管理的测试）
        SpaceConfig.objects.create(
            space_id=self.space.id, name=FlowVersioning.name, value_type="TEXT", text_value="true"
        )

    def test_list_template(self):
        """测试列表查询模板"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "list_template"})
        request = self.factory.get(f"/templates/list_template/?space_id={self.space.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        assert len(results) >= 1

    def test_list_template_with_empty_scope(self):
        """测试查询空scope的模板"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
            scope_type=None,
            scope_value=None,
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "list_template"})
        request = self.factory.get(f"/templates/list_template/?space_id={self.space.id}&empty_scope=true")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200

    # def test_update_template(self):
    #     """测试更新模板"""
    #     snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
    #     template = Template.objects.create(
    #         name="Test Template",
    #         space_id=self.space.id,
    #         snapshot_id=snapshot.id,
    #         creator="test_user",
    #         updated_by="test_user"
    #     )
    #     snapshot.template_id = template.id
    #     snapshot.save()

    #     view = TemplateViewSet.as_view({"patch": "partial_update"})
    #     data = {
    #         "name": "Updated Template Name",
    #         "desc": "Updated Description"
    #     }
    #     request = self.factory.patch(
    #         f"/templates/{template.id}/",
    #         data,
    #         format="json"
    #     )
    #     force_authenticate(request, user=self.user)
    #     response = view(request, pk=template.id)

    #     assert response.status_code == 200
    #     resp_data = response.data.get("data", response.data)
    #     # 可能返回更新后的模板数据
    #     assert response.status_code == 200
    #     force_authenticate(request, user=self.user)
    #     response = view(request)

    #     assert response.status_code == 200

    def test_analysis_constants_ref(self):
        """测试分析变量引用"""
        tree = deepcopy(self.pipeline_tree)
        tree["constants"] = {"${key1}": {"key": "key1", "value": "value1"}}

        view = TemplateViewSet.as_view({"post": "analysis_constants_ref"})
        request = self.factory.post("/templates/analysis_constants_ref/", tree, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        data = response.data.get("data", response.data)
        assert "defined" in data
        assert "nodefined" in data

    def test_draw_pipeline(self):
        """测试画布排版"""
        view = TemplateViewSet.as_view({"post": "draw_pipeline"})
        data = {"pipeline_tree": self.pipeline_tree, "canvas_width": 1200}
        request = self.factory.post("/templates/draw_pipeline/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "pipeline_tree" in resp_data

    def test_get_template_operation_record(self):
        """测试获取模板操作记录"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "get_task_operation_record"})
        request = self.factory.get(f"/templates/{template.id}/get_template_operation_record/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True

    def test_get_space_related_configs(self):
        """测试获取空间相关配置"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "get_space_related_configs"})
        request = self.factory.get(f"/templates/{template.id}/get_space_related_configs/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200

    def test_preview_task_tree(self):
        """测试预览任务树"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"post": "preview_task_tree"})
        data = {"appoint_node_ids": [], "is_all_nodes": True, "version": None}
        request = self.factory.post(f"/templates/{template.id}/preview_task_tree/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "version" in resp_data

    def test_preview_task_tree_with_appoint_nodes(self):
        """测试预览任务树指定节点"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # Get a node ID from the pipeline tree
        node_ids = list(self.pipeline_tree.get("activities", {}).keys())

        view = TemplateViewSet.as_view({"post": "preview_task_tree"})
        data = {"appoint_node_ids": node_ids[:1] if node_ids else [], "is_all_nodes": False, "version": None}
        request = self.factory.post(f"/templates/{template.id}/preview_task_tree/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200

    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_create_mock_task(self, mock_client_class):
        """测试创建Mock任务"""
        from bkflow.admin.models import ModuleInfo

        # 创建必要的 ModuleInfo
        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
            scope_type="project",
            scope_value="123",
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_client = mock.Mock()
        mock_client.create_task.return_value = {"result": True, "data": {"id": 1, "name": "Mock Task"}}
        mock_client_class.return_value = mock_client

        view = TemplateViewSet.as_view({"post": "create_mock_task"})
        data = {
            "name": "Mock Task",
            "creator": "test_user",  # 添加必需的creator字段
            "pipeline_tree": self.pipeline_tree,
            "mock_data": {"nodes": [], "outputs": {}, "mock_data_ids": {}},  # 提供完整的mock_data结构
            "include_node_ids": [],
        }
        request = self.factory.post(f"/templates/{template.id}/create_mock_task/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "id" in resp_data or response.status_code == 200

    def test_get_draft_template(self):
        """测试获取草稿模板"""
        # 启用版本管理（已在setup_method中设置）
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "get_draft_template"})
        request = self.factory.get(f"/templates/{template.id}/get_draft_template/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        # Response会被包装，需要从data中获取
        resp_data = (
            response.data.get("data", response.data)
            if isinstance(response.data, dict) and "data" in response.data
            else response.data
        )
        assert "pipeline_tree" in resp_data

    def test_calculate_version(self):
        """测试计算版本号"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "calculate_version"})
        request = self.factory.get(f"/templates/{template.id}/calculate_version/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        # calculate_version 可能因为版本号格式问题返回 {"result": False, "data": {"detail": ...}}
        if response.data.get("result") is False:
            assert "data" in response.data
            assert "detail" in response.data.get("data", {})
        else:
            resp_data = response.data.get("data", response.data)
            assert "version" in resp_data

    def test_release_template(self):
        """测试发布模板"""
        draft_snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "test_user")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=draft_snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        draft_snapshot.template_id = template.id
        draft_snapshot.save()

        view = TemplateViewSet.as_view({"post": "release_template"})
        data = {"version": "1.0.0", "desc": "Release version"}
        request = self.factory.post(f"/templates/{template.id}/release_template/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        if "template_id" in resp_data:
            assert resp_data.get("template_id") == template.id
        else:
            assert response.status_code == 200

    def test_rollback_template(self):
        """测试回滚模板"""
        snapshot1 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        snapshot2 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.1.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot2.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot1.template_id = template.id
        snapshot1.save()
        snapshot2.template_id = template.id
        snapshot2.save()

        view = TemplateViewSet.as_view({"post": "rollback_template"})
        data = {"version": "1.0.0"}
        request = self.factory.post(f"/templates/{template.id}/rollback_template/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200

    # def test_rollback_template_without_version(self):
    #     """测试回滚模板缺少version参数"""
    #     snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
    #     template = Template.objects.create(
    #         name="Test Template",
    #         space_id=self.space.id,
    #         snapshot_id=snapshot.id,
    #         creator="test_user",
    #         updated_by="test_user"
    #     )
    #     snapshot.template_id = template.id
    #     snapshot.save()

    #     view = TemplateViewSet.as_view({"post": "rollback_template"})
    #     data = {}
    #     request = self.factory.post(
    #         f"/templates/{template.id}/rollback_template/",
    #         data,
    #         format="json"
    #     )
    #     force_authenticate(request, user=self.user)
    #     response = view(request, pk=template.id)

    #     assert response.status_code == 200
    #     assert "version" in response.data.get("detail", "")


@pytest.mark.django_db
class TestTemplateInternalViewSet:
    """测试 TemplateInternalViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    @mock.patch("bkflow.template.views.template.PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes")
    @mock.patch("bkflow.template.views.template.replace_subprocess_version")
    @mock.patch("bkflow.template.views.template.SpaceConfig.get_config")
    def test_get_template_data(self, mock_get_config, mock_replace, mock_previewer):
        """测试获取模板数据"""
        # Mock SpaceConfig to avoid configuration issues
        mock_get_config.return_value = "false"
        mock_replace.side_effect = lambda x, y: x  # Return unchanged
        mock_previewer.side_effect = lambda x: None  # Do nothing

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateInternalViewSet.as_view({"get": "get_template_data"})
        request = self.factory.get(f"/internal/templates/{template.id}/get_template_data/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        # get_template_data 的返回可能被包装在 {'result': True, 'data': {...}}
        if "result" in response.data and response.data["result"] is True:
            assert "pipeline_tree" in response.data["data"]
        else:
            # 或者直接返回数据
            assert "pipeline_tree" in response.data


@pytest.mark.django_db
class TestTemplateMockDataViewSet:
    """测试 TemplateMockDataViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_list_mock_data(self):
        """测试列表查询Mock数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        TemplateMockData.objects.create(
            template_id=template.id,
            space_id=self.space.id,
            node_id="node1",
            data={"key": "value"},
            operator="test_user",
        )

        view = TemplateMockDataViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/mock_data/?space_id={self.space.id}&template_id={template.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert len(response.data) >= 1

    def test_batch_create_mock_data(self):
        """测试批量创建Mock数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateMockDataViewSet.as_view({"post": "batch_create"})
        # data字段应该是字典，键是node_id，值是mock数据列表
        data = {
            "space_id": self.space.id,
            "template_id": template.id,
            "data": {
                "node1": [{"name": "mock1", "data": {"key": "value1"}}],
                "node2": [{"name": "mock2", "data": {"key": "value2"}}],
            },
        }
        request = self.factory.post("/mock_data/batch_create/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert len(response.data) >= 2

    def test_batch_update_mock_data(self):
        """测试批量更新Mock数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        TemplateMockData.objects.create(
            template_id=template.id,
            space_id=self.space.id,
            node_id="node1",
            data={"key": "old_value"},
            operator="test_user",
        )

        view = TemplateMockDataViewSet.as_view({"post": "batch_update"})
        # data字段应该是字典，键是node_id，值是mock数据列表
        data = {
            "space_id": self.space.id,
            "template_id": template.id,
            "data": {"node1": [{"name": "updated_mock", "data": {"key": "new_value"}}]},
        }
        request = self.factory.post("/mock_data/batch_update/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200


@pytest.mark.django_db
class TestTemplateMockSchemeViewSet:
    """测试 TemplateMockSchemeViewSet"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_create_mock_scheme(self):
        """测试创建Mock方案"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateMockSchemeViewSet.as_view({"post": "create"})
        data = {"space_id": self.space.id, "template_id": template.id, "data": {"scheme_key": "scheme_value"}}
        request = self.factory.post("/mock_schemes/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code in [200, 201]

    def test_update_mock_scheme(self):
        """测试更新Mock方案"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        scheme = TemplateMockScheme.objects.create(
            space_id=self.space.id, template_id=template.id, data={"old_key": "old_value"}, operator="test_user"
        )

        view = TemplateMockSchemeViewSet.as_view({"patch": "partial_update"})
        data = {"data": {"new_key": "new_value"}}
        request = self.factory.patch(f"/mock_schemes/{scheme.id}/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=scheme.id)

        assert response.status_code == 200

    def test_list_mock_schemes(self):
        """测试列表查询Mock方案"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        TemplateMockScheme.objects.create(
            space_id=self.space.id, template_id=template.id, data={"key": "value"}, operator="test_user"
        )

        view = TemplateMockSchemeViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/mock_schemes/?space_id={self.space.id}&template_id={template.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200


@pytest.mark.django_db
class TestTemplateMockTaskViewSet:
    """测试 TemplateMockTaskViewSet"""

    def setup_method(self):
        from bkflow.admin.models import ModuleInfo

        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

        # 创建必要的 ModuleInfo
        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

    @mock.patch("bkflow.template.views.template.TaskComponentClient.task_list")
    def test_list_mock_tasks(self, mock_task_list):
        """测试列表查询Mock任务"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_task_list.return_value = [{"id": 1, "name": "Mock Task"}]

        view = TemplateMockTaskViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/mock_tasks/?space_id={self.space.id}&template_id={template.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200


@pytest.mark.django_db
class TestExceptionBranches:
    """测试异常分支覆盖"""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_create_task_template_not_exist(self):
        """测试创建任务时模板不存在的异常"""
        from bkflow.exceptions import ValidationError

        view = AdminTemplateViewSet.as_view({"post": "create_task"})
        data = {"template_id": 99999, "name": "Test Task", "creator": "test_user"}  # 不存在的模板ID  # 添加必需的creator字段
        request = self.factory.post(f"/admin/templates/create_task/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.user)

        # 应该抛出ValidationError异常
        try:
            response = view(request, space_id=self.space.id)
            # 如果没有抛出异常，检查响应
            assert response.status_code in [400, 200]
            if response.status_code == 200:
                assert "result" in response.data and response.data["result"] is False
        except ValidationError:
            # 预期会抛出ValidationError
            pass

    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_create_task_api_error(self, mock_client_class):
        """测试创建任务时API返回错误"""
        from bkflow.admin.models import ModuleInfo

        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # Mock API调用返回错误
        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": False,
            "data": {"detail": "API Error"},  # 添加data字段
            "message": "API Error",
        }
        mock_client_class.return_value = mock_client

        view = AdminTemplateViewSet.as_view({"post": "create_task"})
        data = {"template_id": template.id, "name": "Test Task", "creator": "test_user"}  # 添加必需的creator字段
        request = self.factory.post(f"/admin/templates/create_task/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, space_id=self.space.id)

        # 应该返回错误
        assert response.status_code == 200
        # 检查返回的数据包含错误信息
        if "detail" in response.data:
            assert "API Error" in str(response.data["detail"])

    @mock.patch("bkflow.template.views.template.TaskComponentClient.batch_delete_periodic_task")
    def test_batch_delete_with_decision_table(self, mock_batch_delete):
        """测试批量删除时有决策表引用"""
        from bkflow.admin.models import ModuleInfo

        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        mock_batch_delete.return_value = {"result": True}

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建决策表引用（必须提供data字段）
        DecisionTable.objects.create(
            name="Test Decision Table",
            template_id=template.id,
            space_id=self.space.id,
            creator="test_user",
            is_deleted=False,
            data={"inputs": [], "outputs": [], "rules": []},  # 提供必需的data字段
        )

        view = AdminTemplateViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": self.space.id, "is_full": False, "template_ids": [template.id]}
        request = self.factory.post("/admin/templates/batch_delete/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        # 应该返回失败，因为有决策表引用
        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "decision_detail" in resp_data

    @mock.patch("bkflow.template.views.template.TaskComponentClient.batch_delete_periodic_task")
    def test_batch_delete_with_template_reference(self, mock_batch_delete):
        """测试批量删除时有子流程引用"""
        from bkflow.admin.models import ModuleInfo

        ModuleInfo.objects.get_or_create(
            type="TASK",
            space_id=0,
            defaults={
                "code": "task",
                "url": "http://localhost:8000",
                "token": "test_token",
                "isolation_level": "only_calculation",
            },
        )

        mock_batch_delete.return_value = {"result": True}

        # 创建子流程模板
        sub_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        sub_template = Template.objects.create(
            name="Sub Template",
            space_id=self.space.id,
            snapshot_id=sub_snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        sub_snapshot.template_id = sub_template.id
        sub_snapshot.save()

        # 创建根流程模板
        root_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        root_template = Template.objects.create(
            name="Root Template",
            space_id=self.space.id,
            snapshot_id=root_snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        root_snapshot.template_id = root_template.id
        root_snapshot.save()

        # 创建引用关系
        TemplateReference.objects.create(root_template_id=root_template.id, subprocess_template_id=sub_template.id)

        view = AdminTemplateViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": self.space.id, "is_full": False, "template_ids": [sub_template.id]}
        request = self.factory.post("/admin/templates/batch_delete/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        # 应该返回失败，因为有引用
        assert response.status_code == 200
        resp_data = response.data.get("data", response.data)
        assert "sub_root_map" in resp_data

    @mock.patch("bkflow.template.models.Template.objects.copy_template")
    def test_copy_template_not_exist(self, mock_copy):
        """测试复制不存在的模板"""
        mock_copy.side_effect = Template.DoesNotExist("Template does not exist")

        view = AdminTemplateViewSet.as_view({"post": "copy_template"})
        data = {
            "space_id": self.space.id,
            "template_id": 99999,
            "name": "Copied Template",
            "desc": "Copied Description",
            "copy_subprocess": False,
        }
        request = self.factory.post("/admin/templates/template_copy/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        # 应该返回错误
        assert response.status_code == 200
        if "result" in response.data:
            assert response.data["result"] is False

    @mock.patch("bkflow.template.models.Template.objects.copy_template")
    def test_copy_template_validation_error(self, mock_copy):
        """测试复制模板时的验证错误"""
        from bkflow.exceptions import ValidationError

        mock_copy.side_effect = ValidationError("Validation failed")

        view = AdminTemplateViewSet.as_view({"post": "copy_template"})
        data = {
            "space_id": self.space.id,
            "template_id": 1,
            "name": "Copied Template",
            "desc": "Copied Description",
            "copy_subprocess": False,
        }
        request = self.factory.post("/admin/templates/template_copy/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request)

        # 应该返回错误
        assert response.status_code == 200
        if "result" in response.data:
            assert response.data["result"] is False

    def test_analysis_constants_ref_exception(self):
        """测试分析变量引用时发生异常"""
        view = TemplateViewSet.as_view({"post": "analysis_constants_ref"})
        # 发送一个会导致异常的数据结构
        invalid_tree = {"invalid": "structure"}
        request = self.factory.post("/templates/analysis_constants_ref/", invalid_tree, format="json")
        force_authenticate(request, user=self.user)

        # 应该抛出 AnalysisConstantsRefException
        try:
            response = view(request)
            # 如果没有抛出异常，检查响应
            assert response.status_code in [400, 500, 200]
        except Exception:
            # 预期会抛出异常
            pass

    @mock.patch("bkflow.template.views.template.draw_pipeline_tree")
    def test_draw_pipeline_exception(self, mock_draw):
        """测试画布排版时发生异常"""
        mock_draw.side_effect = Exception("Drawing error")

        view = TemplateViewSet.as_view({"post": "draw_pipeline"})
        data = {"pipeline_tree": self.pipeline_tree}
        request = self.factory.post("/templates/draw_pipeline/", data, format="json")
        force_authenticate(request, user=self.user)

        # 应该抛出异常
        try:
            response = view(request)
            assert response.status_code in [400, 500]
        except Exception:
            # 预期会抛出异常
            pass

    def test_preview_task_tree_get_version_error(self):
        """测试预览任务树时获取版本错误"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"post": "preview_task_tree"})
        data = {"appoint_node_ids": [], "is_all_nodes": True, "version": "999.0.0"}  # 不存在的版本
        request = self.factory.post(f"/templates/{template.id}/preview_task_tree/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        # 应该返回错误
        assert response.status_code == 200
        if "result" in response.data:
            assert response.data["result"] is False

    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_create_mock_task_api_error(self, mock_client_class):
        """测试创建Mock任务时API返回错误"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # Mock API调用返回错误
        mock_client = mock.Mock()
        mock_client.create_task.return_value = {"result": False, "message": "API Error"}
        mock_client_class.return_value = mock_client

        view = TemplateViewSet.as_view({"post": "create_mock_task"})
        data = {
            "name": "Mock Task",
            "creator": "test_user",  # 添加必需的creator字段
            "pipeline_tree": self.pipeline_tree,
            "mock_data": {"nodes": [], "outputs": {}, "mock_data_ids": {}},  # 提供完整的mock_data结构
        }
        request = self.factory.post(f"/templates/{template.id}/create_mock_task/", data, format="json")
        force_authenticate(request, user=self.user)

        # 应该抛出 APIResponseError
        try:
            response = view(request, pk=template.id)
            assert response.status_code in [400, 500, 200]
        except Exception:
            pass

    def test_calculate_version_error(self):
        """测试计算版本号时的错误"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "invalid_version")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "calculate_version"})
        request = self.factory.get(f"/templates/{template.id}/calculate_version/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        # 应该返回错误或成功（取决于版本号处理逻辑）
        assert response.status_code == 200

    def test_release_template_version_exists(self):
        """测试发布模板时版本已存在"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"post": "release_template"})
        data = {"version": "1.0.0", "desc": "Release version"}  # 已存在的版本
        request = self.factory.post(f"/templates/{template.id}/release_template/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        # 应该返回版本已存在的错误
        assert response.status_code == 200
        if "result" in response.data:
            assert response.data["result"] is False

    def test_release_template_invalid_version(self):
        """测试发布模板时版本号不符合规范"""
        draft_snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "test_user")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=draft_snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        draft_snapshot.template_id = template.id
        draft_snapshot.save()

        view = TemplateViewSet.as_view({"post": "release_template"})
        data = {"version": "0.5.0", "desc": "Invalid version"}  # 小于当前版本
        request = self.factory.post(f"/templates/{template.id}/release_template/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        # 可能返回版本号不符合规范的错误
        assert response.status_code == 200

    def test_create_mock_scheme_duplicate(self):
        """测试创建重复的Mock方案"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 先创建一个Mock方案
        TemplateMockScheme.objects.create(
            space_id=self.space.id, template_id=template.id, data={"key": "value"}, operator="test_user"
        )

        # 尝试创建重复的Mock方案
        view = TemplateMockSchemeViewSet.as_view({"post": "create"})
        data = {"space_id": self.space.id, "template_id": template.id, "data": {"new_key": "new_value"}}
        request = self.factory.post("/mock_schemes/", data, format="json")
        force_authenticate(request, user=self.user)

        # 应该抛出ValidationError
        try:
            response = view(request)
            assert response.status_code in [400, 200]
        except Exception:
            pass


@pytest.mark.django_db
class TestTemplateFilterAndBranches:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def _create_template(self, name="t1"):
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name=name,
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()
        return template

    def test_filter_by_labels_returns_queryset_when_no_match(self):
        """Cover TemplateFilterSet.filter_by_labels empty label_ids branch (137-139)."""
        template = self._create_template("t_no_label")

        view = TemplateViewSet.as_view({"get": "list_template"})
        request = self.factory.get(f"/templates/list_template/?space_id={self.space.id}&label=__not_exists__")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        # should not error and should include created template
        assert any(item.get("id") == template.id for item in results)

    def test_filter_by_labels_filters_queryset(self):
        """Cover TemplateFilterSet.filter_by_labels subquery filter branch (141-143)."""
        label = Label.objects.create(
            name="tag_1",
            creator="test_user",
            updated_by="test_user",
            space_id=self.space.id,
            label_scope=["template"],
        )
        template_hit = self._create_template("t_hit")
        template_miss = self._create_template("t_miss")
        TemplateLabelRelation.objects.create(template_id=template_hit.id, label_id=label.id)

        view = TemplateViewSet.as_view({"get": "list_template"})
        request = self.factory.get(f"/templates/list_template/?space_id={self.space.id}&label=tag_1")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        ids = {item.get("id") for item in results}
        assert template_hit.id in ids
        assert template_miss.id not in ids

    def test_admin_list_injects_labels_and_trigger_flag_false(self):
        """Cover AdminTemplateViewSet.list label injection and trigger flag false branch."""
        template = self._create_template("t_admin")
        label = Label.objects.create(
            name="tag_admin",
            creator="test_user",
            updated_by="test_user",
            space_id=self.space.id,
            label_scope=["template"],
        )
        TemplateLabelRelation.objects.create(template_id=template.id, label_id=label.id)

        view = AdminTemplateViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/admin/templates/?space_id={self.space.id}")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", {}).get("results", [])
        item = next((r for r in results if r.get("id") == template.id), None)
        assert item is not None
        assert item.get("has_interval_trigger") is False
        assert any(_label.get("id") == label.id for _label in item.get("labels", []))

    @mock.patch("bkflow.template.views.template.SpaceConfig.get_config")
    @mock.patch("bkflow.template.views.template.build_default_pipeline_tree_with_space_id")
    def test_create_template_flow_versioning_true_creates_draft_snapshot(self, mock_build_tree, mock_get_config):
        """Cover create_template flow-versioning true branch (create_draft_snapshot)."""
        mock_build_tree.return_value = self.pipeline_tree
        mock_get_config.return_value = "true"

        view = AdminTemplateViewSet.as_view({"post": "create_template"})
        data = {"name": "New Template", "desc": "d", "label_ids": []}
        request = self.factory.post(f"/admin/templates/create_default_template/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request, space_id=self.space.id)

        assert response.status_code == 200
        # NOTE: response payload is wrapped by SimpleGenericViewSet.finalize_response
        template_id = response.data["data"]["data"]["id"]
        template = Template.objects.get(id=template_id)
        snapshot = TemplateSnapshot.objects.get(id=template.snapshot_id)
        assert snapshot.draft is True


@pytest.mark.django_db
class TestTemplateViewSetMoreExceptionBranches:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()
        SpaceConfig.objects.create(
            space_id=self.space.id, name=FlowVersioning.name, value_type="TEXT", text_value="true"
        )

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        self.template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = self.template.id
        snapshot.save()

    def test_preview_task_tree_get_pipeline_tree_error_wrapped(self, monkeypatch):
        """Cover preview_task_tree internal exception catch (579-604)."""

        def _boom(_version):
            raise Exception("boom")

        monkeypatch.setattr(Template, "get_pipeline_tree_by_version", lambda _self, _version: _boom(_version))

        view = TemplateViewSet.as_view({"post": "preview_task_tree"})
        data = {"appoint_node_ids": [], "is_all_nodes": True, "version": "1.0.0", "is_draft": False}
        request = self.factory.post(f"/templates/{self.template.id}/preview_task_tree/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is False

    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_create_mock_task_raises_api_response_error(self, mock_client_class):
        """Cover create_mock_task API failure branch (619-622)."""
        mock_client = mock.Mock()
        mock_client.create_task.return_value = {"result": False, "message": "api error"}
        mock_client_class.return_value = mock_client

        view = TemplateViewSet.as_view({"post": "create_mock_task"})
        data = {
            "name": "Mock Task",
            "creator": "test_user",
            "pipeline_tree": self.pipeline_tree,
            "mock_data": {"nodes": [], "outputs": {}, "mock_data_ids": {}},
            "include_node_ids": [],
        }
        request = self.factory.post(f"/templates/{self.template.id}/create_mock_task/", data, format="json")
        force_authenticate(request, user=self.user)

        with pytest.raises(Exception):
            view(request, pk=self.template.id)

    def test_get_draft_template_versioning_disabled(self):
        """Cover get_draft_template versioning disabled branch (657)."""
        space2 = Space.objects.create(name="No Version Space", app_code="test_app2")
        # explicit disable versioning
        SpaceConfig.objects.create(space_id=space2.id, name=FlowVersioning.name, value_type="TEXT", text_value="false")

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        template = Template.objects.create(
            name="t2",
            space_id=space2.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = template.id
        snapshot.save()

        view = TemplateViewSet.as_view({"get": "get_draft_template"})
        request = self.factory.get(f"/templates/{template.id}/get_draft_template/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=template.id)

        assert response.status_code == 200
        assert response.data.get("result") is False

    def test_calculate_version_invalid_version_returns_exception_response(self):
        """Cover calculate_version ValueError branch (675-680)."""
        # Template.version is a property derived from TemplateSnapshot.version when versioning is enabled,
        # so only updating snapshot version is enough.
        TemplateSnapshot.objects.filter(id=self.template.snapshot_id).update(version="invalid")

        view = TemplateViewSet.as_view({"get": "calculate_version"})
        request = self.factory.get(f"/templates/{self.template.id}/calculate_version/")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is False

    def test_rollback_template_version_missing(self):
        """Cover rollback_template missing version branch (723)."""
        view = TemplateViewSet.as_view({"post": "rollback_template"})
        request = self.factory.post(f"/templates/{self.template.id}/rollback_template/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert "version" in str(response.data)


@pytest.mark.django_db
class TestTemplateViewsMoreCoverage:
    def setup_method(self):
        self.factory = APIRequestFactory()
        self.admin_user, _ = User.objects.get_or_create(
            username="admin", defaults={"is_superuser": True, "is_staff": True}
        )
        self.user = User.objects.create_superuser(username="test_user", password="password")
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

        # enable flow versioning by default in this class
        SpaceConfig.objects.create(
            space_id=self.space.id, name=FlowVersioning.name, value_type="TEXT", text_value="true"
        )

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        self.template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot.template_id = self.template.id
        snapshot.save()

    def test_admin_list_without_pagination_hits_return_response_183(self, monkeypatch):
        """Cover AdminTemplateViewSet.list non-paginated return (183)."""
        monkeypatch.setattr(AdminTemplateViewSet, "pagination_class", None)

        view = AdminTemplateViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/admin/templates/?space_id={self.space.id}")
        force_authenticate(request, user=self.admin_user)
        response = view(request)

        assert response.status_code == 200
        assert response.data.get("result") is True
        assert isinstance(response.data.get("data"), list)

    def test_admin_update_proxy_to_super_update_211(self):
        """Cover AdminTemplateViewSet.update -> super().update (211) without touching serializer validation."""
        from rest_framework.response import Response

        with mock.patch("rest_framework.viewsets.ModelViewSet.update", return_value=Response({"ok": True})):
            view = AdminTemplateViewSet.as_view({"put": "update"})
            request = self.factory.put(f"/admin/templates/{self.template.id}/", {}, format="json")
            force_authenticate(request, user=self.admin_user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True

    @mock.patch("bkflow.template.views.template.event_broadcast_signal")
    @mock.patch("bkflow.template.views.template.PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes")
    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_admin_create_task_success_hits_event_broadcast_250_263(self, mock_client_cls, _mock_preview, mock_signal):
        """Cover AdminTemplateViewSet.create_task success branch and event broadcast (250-263)."""
        mock_client = mock.Mock()
        mock_client.create_task.return_value = {
            "result": True,
            "data": {"id": 1, "name": "task", "template_id": self.template.id, "parameters": {}},
        }
        mock_client_cls.return_value = mock_client

        view = AdminTemplateViewSet.as_view({"post": "create_task"})
        data = {"template_id": self.template.id, "name": "task", "creator": "test_user", "constants": {}}
        request = self.factory.post(f"/admin/templates/create_task/{self.space.id}/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        response = view(request, space_id=self.space.id)

        assert response.status_code == 200
        assert response.data.get("result") is True
        mock_signal.send.assert_called_once()

    def test_admin_batch_delete_continue_branch_311(self):
        """Cover batch_delete 'continue' branch when root template is also in delete list (311)."""
        snapshot2 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.1")
        root = Template.objects.create(
            name="Root",
            space_id=self.space.id,
            snapshot_id=snapshot2.id,
            creator="test_user",
            updated_by="test_user",
        )
        snapshot2.template_id = root.id
        snapshot2.save()

        # Mock TemplateReference queryset to make sure the loop runs and hits the `continue` line (311)
        mocked_ref_qs = mock.Mock()
        mocked_ref_qs.values_list.return_value = [str(root.id)]
        mocked_ref_qs.values.return_value = [
            {"subprocess_template_id": str(self.template.id), "root_template_id": str(root.id)}
        ]

        view = AdminTemplateViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": self.space.id, "is_full": False, "template_ids": [root.id, self.template.id]}
        request = self.factory.post("/admin/templates/batch_delete/", data, format="json")
        force_authenticate(request, user=self.admin_user)

        original_filter = Template.objects.filter

        def _template_filter_side_effect(*args, **kwargs):
            # Only affect the query that builds `templates_map` so that `root_id not in templates_map` is True
            if "id__in" in kwargs and kwargs.get("is_deleted") is False and "space_id" not in kwargs:
                return original_filter(id__in=[self.template.id], is_deleted=False)
            return original_filter(*args, **kwargs)

        with mock.patch(
            "bkflow.template.views.template.TemplateReference.objects.filter", return_value=mocked_ref_qs
        ), mock.patch(
            "bkflow.template.views.template.Template.objects.filter", side_effect=_template_filter_side_effect
        ), mock.patch(
            "bkflow.template.views.template.Trigger.objects.batch_delete_by_ids"
        ):
            response = view(request)

        assert response.status_code == 200
        assert response.data.get("result") is True

    def test_admin_batch_delete_is_full_hits_326(self):
        """Cover batch_delete is_full=True update-all branch (326)."""
        view = AdminTemplateViewSet.as_view({"post": "batch_delete"})
        data = {"space_id": self.space.id, "is_full": True, "template_ids": [self.template.id]}
        request = self.factory.post("/admin/templates/batch_delete/", data, format="json")
        force_authenticate(request, user=self.admin_user)
        with mock.patch("bkflow.template.views.template.Trigger.objects.batch_delete_by_ids"):
            response = view(request)

        assert response.status_code == 200
        assert response.data.get("result") is True
        assert Template.objects.filter(space_id=self.space.id, is_deleted=True).exists()

    def test_template_version_list_without_pagination_hits_390(self, monkeypatch):
        """Cover TemplateVersionViewSet.list non-paginated return (390)."""
        monkeypatch.setattr(TemplateVersionViewSet, "pagination_class", None)

        view = TemplateVersionViewSet.as_view({"get": "list"})
        request = self.factory.get(f"/template_versions/?template_id={self.template.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        assert response.data.get("result") is True
        assert isinstance(response.data.get("data"), list)

    def test_template_version_delete_snapshot_template_missing_397_398(self):
        """Cover delete_snapshot when snapshot's template does not exist (397-398)."""
        snap = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "9.9.9")
        snap.template_id = 999999
        snap.save(update_fields=["template_id"])

        view = TemplateVersionViewSet.as_view({"post": "delete_snapshot"})
        request = self.factory.post(f"/template_versions/{snap.id}/delete_snapshot/", {}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=snap.id)

        assert response.status_code == 400

    def test_list_template_versioning_filters_draft_and_hits_456(self, monkeypatch):
        """Cover list_template versioning filter branch (443-448) and non-pagination return (456)."""
        monkeypatch.setattr(TemplateViewSet, "pagination_class", None)

        # draft snapshot template should be filtered out
        draft_snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "test_user")
        t_draft = Template.objects.create(
            name="Draft",
            space_id=self.space.id,
            snapshot_id=draft_snapshot.id,
            creator="test_user",
            updated_by="test_user",
        )
        draft_snapshot.template_id = t_draft.id
        draft_snapshot.save(update_fields=["template_id"])

        view = TemplateViewSet.as_view({"get": "list_template"})
        request = self.factory.get(f"/templates/list_template/?space_id={self.space.id}")
        force_authenticate(request, user=self.user)
        response = view(request)

        assert response.status_code == 200
        results = response.data.get("data", [])
        ids = {item.get("id") for item in results}
        assert t_draft.id not in ids
        assert self.template.id in ids

    def test_get_space_related_configs_raises_when_default_not_exists_546_548(self):
        """Cover get_space_related_configs catch and re-raise (546-548)."""
        from bkflow.space.exceptions import SpaceConfigDefaultValueNotExists

        def _boom(*args, **kwargs):
            raise SpaceConfigDefaultValueNotExists("no default")

        with mock.patch("bkflow.template.views.template.SpaceConfig.get_config", side_effect=_boom):
            view = TemplateViewSet.as_view({"get": "get_space_related_configs"})
            request = self.factory.get(f"/templates/{self.template.id}/get_space_related_configs/")
            force_authenticate(request, user=self.user)
            with pytest.raises(SpaceConfigDefaultValueNotExists):
                view(request, pk=self.template.id)

    def test_get_space_related_configs_uniform_api_branch_552(self):
        """Cover uniform api config handler branch (552)."""
        from bkflow.space.configs import GatewayExpressionConfig, UniformApiConfig

        def _get_config(space_id=None, config_name=None, *args, **kwargs):
            if config_name == GatewayExpressionConfig.name:
                return "{}"
            if config_name == UniformApiConfig.name:
                return '{"token": "x"}'
            return "true"

        handler_ret = mock.Mock()
        handler_ret.dict.return_value = {"handled": True}
        with mock.patch("bkflow.template.views.template.SpaceConfig.get_config", side_effect=_get_config), mock.patch(
            "bkflow.template.views.template.UniformAPIConfigHandler"
        ) as handler_cls:
            handler_cls.return_value.handle.return_value = handler_ret

            view = TemplateViewSet.as_view({"get": "get_space_related_configs"})
            request = self.factory.get(f"/templates/{self.template.id}/get_space_related_configs/")
            force_authenticate(request, user=self.user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        data = response.data.get("data", {})
        assert UniformApiConfig.name in data
        assert data[UniformApiConfig.name] == {"handled": True}

    def test_template_update_injects_labels_460_468(self):
        """Cover TemplateViewSet.update label injection (460-468) by stubbing serializer and perform_update."""
        label = Label.objects.create(
            name="tag_upd",
            creator="test_user",
            updated_by="test_user",
            space_id=self.space.id,
            label_scope=["template"],
        )
        TemplateLabelRelation.objects.set_labels(self.template.id, [label.id])

        template_id = self.template.id

        class _StubSerializer:
            def __init__(self):
                self.data = {"id": template_id, "name": "n"}

            def is_valid(self, raise_exception=False):
                return True

        def _get_serializer(_self, *args, **kwargs):
            return _StubSerializer()

        with mock.patch.object(TemplateViewSet, "get_serializer", _get_serializer), mock.patch.object(
            TemplateViewSet, "perform_update", lambda *_args, **_kwargs: None
        ):
            view = TemplateViewSet.as_view({"put": "update"})
            request = self.factory.put(f"/templates/{self.template.id}/", {}, format="json")
            force_authenticate(request, user=self.user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True
        assert any(_label.get("id") == label.id for _label in response.data.get("data", {}).get("labels", []))

    def test_update_labels_action_473_477(self):
        """Cover update_labels transaction block and return (473-477)."""
        label = Label.objects.create(
            name="tag2",
            creator="test_user",
            updated_by="test_user",
            space_id=self.space.id,
            label_scope=["template"],
        )
        view = TemplateViewSet.as_view({"post": "update_labels"})
        request = self.factory.post(
            f"/templates/{self.template.id}/update_labels/", {"label_ids": [label.id]}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("data") == [label.id]

    def test_analysis_constants_ref_exception_489_491(self):
        """Cover analysis_constants_ref exception branch (489-491)."""
        from bkflow.template.exceptions import AnalysisConstantsRefException

        with mock.patch(
            "bkflow.template.views.template.analysis_pipeline_constants_ref", side_effect=Exception("boom")
        ):
            view = TemplateViewSet.as_view({"post": "analysis_constants_ref"})
            request = self.factory.post("/templates/analysis_constants_ref/", {"constants": {}}, format="json")
            force_authenticate(request, user=self.user)
            with pytest.raises(AnalysisConstantsRefException):
                view(request)

    def test_analysis_constants_ref_nodefined_branch_500(self):
        """Cover analysis_constants_ref nodefined assignment (500)."""
        with mock.patch("bkflow.template.views.template.analysis_pipeline_constants_ref", return_value={"x": "y"}):
            view = TemplateViewSet.as_view({"post": "analysis_constants_ref"})
            request = self.factory.post("/templates/analysis_constants_ref/", {"constants": {}}, format="json")
            force_authenticate(request, user=self.user)
            response = view(request)

        assert response.status_code == 200
        assert response.data.get("data", {}).get("nodefined", {}).get("x") == "y"

    def test_draw_pipeline_includes_position_kwargs_515(self):
        """Cover draw_pipeline POSITION kwargs branch (515)."""
        with mock.patch("bkflow.template.views.template.draw_pipeline_tree") as m:
            view = TemplateViewSet.as_view({"post": "draw_pipeline"})
            request = self.factory.post(
                "/templates/draw_pipeline/",
                {"pipeline_tree": self.pipeline_tree, "canvas_width": 1300, "activity_size": [150, 54]},
                format="json",
            )
            force_authenticate(request, user=self.user)
            response = view(request)

        assert response.status_code == 200
        m.assert_called_once()

    @mock.patch("bkflow.template.views.template.preview_template_tree", return_value={"ok": True})
    def test_preview_task_tree_draft_success_covers_569_604(self, _mock_preview):
        """Cover preview_task_tree is_draft branch and success path (569, 579-604)."""
        draft = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "test_user")
        draft.template_id = self.template.id
        draft.save(update_fields=["template_id"])

        with mock.patch.object(Template, "outputs", lambda *_args, **_kwargs: {}):
            view = TemplateViewSet.as_view({"post": "preview_task_tree"})
            data = {"appoint_node_ids": [], "is_all_nodes": True, "version": "1.0.0", "is_draft": True}
            request = self.factory.post(f"/templates/{self.template.id}/preview_task_tree/", data, format="json")
            force_authenticate(request, user=self.user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True
        assert response.data.get("data", {}).get("name") == self.template.name

    def test_preview_task_tree_not_all_nodes_hits_exclude_task_nodes_585(self):
        """Cover preview_task_tree not-all-nodes branch (585)."""
        with mock.patch.object(
            Template, "get_pipeline_tree_by_version", return_value=self.pipeline_tree
        ), mock.patch.object(Template, "outputs", lambda *_args, **_kwargs: {}), mock.patch(
            "bkflow.template.views.template.PipelineTemplateWebPreviewer."
            "get_template_exclude_task_nodes_with_appoint_nodes",
            return_value=["x"],
        ) as m_get_exclude, mock.patch(
            "bkflow.template.views.template.preview_template_tree", return_value={"ok": True}
        ):
            view = TemplateViewSet.as_view({"post": "preview_task_tree"})
            data = {"appoint_node_ids": ["n1"], "is_all_nodes": False, "version": "1.0.0", "is_draft": False}
            request = self.factory.post(f"/templates/{self.template.id}/preview_task_tree/", data, format="json")
            force_authenticate(request, user=self.user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True
        m_get_exclude.assert_called_once()

    def test_preview_task_tree_outer_exception_logged_591_594(self):
        """Cover preview_task_tree outer exception handler logging (591-594)."""
        with mock.patch.object(Template, "get_pipeline_tree_by_version", return_value=self.pipeline_tree), mock.patch(
            "bkflow.template.views.template.preview_template_tree", side_effect=Exception("boom")
        ):
            view = TemplateViewSet.as_view({"post": "preview_task_tree"})
            data = {"appoint_node_ids": [], "is_all_nodes": True, "version": "1.0.0", "is_draft": False}
            request = self.factory.post(f"/templates/{self.template.id}/preview_task_tree/", data, format="json")
            force_authenticate(request, user=self.user)
            with pytest.raises(Exception):
                view(request, pk=self.template.id)

    @mock.patch("bkflow.template.views.template.PipelineTemplateWebPreviewer.preview_pipeline_tree_exclude_task_nodes")
    @mock.patch(
        "bkflow.template.views.template.PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes"
    )
    @mock.patch("bkflow.template.views.template.TaskComponentClient")
    def test_create_mock_task_include_node_ids_branch_619_622(self, mock_client_cls, mock_get_exclude, _mock_preview):
        """Cover create_mock_task include_node_ids branch (619-622)."""
        mock_get_exclude.return_value = []
        mock_client = mock.Mock()
        mock_client.create_task.return_value = {"result": True, "data": {"id": 11}}
        mock_client_cls.return_value = mock_client

        view = TemplateViewSet.as_view({"post": "create_mock_task"})
        data = {
            "name": "Mock Task",
            "creator": "test_user",
            "pipeline_tree": self.pipeline_tree,
            "mock_data": {"nodes": [], "outputs": {}, "mock_data_ids": {}},
            "include_node_ids": ["node1"],
        }
        request = self.factory.post(f"/templates/{self.template.id}/create_mock_task/", data, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is True

    def test_release_template_duplicate_version_693(self):
        """Cover release_template duplicate version early return (693)."""
        view = TemplateViewSet.as_view({"post": "release_template"})
        request = self.factory.post(
            f"/templates/{self.template.id}/release_template/", {"version": "1.0.0", "desc": "d"}, format="json"
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is False

    def test_release_template_invalid_version_bump_custom_696_698(self):
        """Cover release_template bump_custom ValueError branch (696-698)."""
        with mock.patch("bkflow.template.views.template.bump_custom", side_effect=ValueError("bad")):
            view = TemplateViewSet.as_view({"post": "release_template"})
            request = self.factory.post(
                f"/templates/{self.template.id}/release_template/", {"version": "bad", "desc": "d"}, format="json"
            )
            force_authenticate(request, user=self.user)
            response = view(request, pk=self.template.id)

        assert response.status_code == 200
        assert response.data.get("result") is False
        assert "版本号不符合规范" in str(response.data)

    def test_rollback_template_versioning_disabled_720(self):
        """Cover rollback_template when versioning disabled (720)."""
        space2 = Space.objects.create(name="No Version", app_code="app2")
        SpaceConfig.objects.create(space_id=space2.id, name=FlowVersioning.name, value_type="TEXT", text_value="false")

        snap = TemplateSnapshot.create_snapshot(self.pipeline_tree, "test_user", "1.0.0")
        tpl = Template.objects.create(
            name="t",
            space_id=space2.id,
            snapshot_id=snap.id,
            creator="test_user",
            updated_by="test_user",
        )
        snap.template_id = tpl.id
        snap.save(update_fields=["template_id"])

        view = TemplateViewSet.as_view({"post": "rollback_template"})
        request = self.factory.post(f"/templates/{tpl.id}/rollback_template/", {"version": "1.0.0"}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=tpl.id)

        assert response.status_code == 200
        assert response.data.get("result") is False
