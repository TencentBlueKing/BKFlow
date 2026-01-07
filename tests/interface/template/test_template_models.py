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

from bkflow.exceptions import ValidationError
from bkflow.space.models import Space
from bkflow.template.models import (
    Template,
    TemplateMockData,
    TemplateReference,
    TemplateSnapshot,
    Trigger,
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
        "constants": {"${key1}": {"key": "key1", "value": "value1", "show_type": "show"}},
        "outputs": ["${key1}"],
    }


@pytest.mark.django_db
class TestTemplateManager:
    """测试 TemplateManager"""

    def setup_method(self):
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_copy_template_without_versioning(self, mock_get_config):
        """测试在非版本管理模式下复制模板"""
        mock_get_config.return_value = "false"

        # 创建原始模板
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        original_template = Template.objects.create(
            name="Original Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        snapshot.template_id = original_template.id
        snapshot.save()

        # 复制模板
        copied_template = Template.objects.copy_template(
            template_id=original_template.id,
            space_id=self.space.id,
            operator="admin",
            name="Copied Template",
            desc="Copied Description",
        )

        # 验证
        assert copied_template.id != original_template.id
        assert copied_template.name == "Copied Template"
        assert copied_template.desc == "Copied Description"
        assert copied_template.space_id == self.space.id
        assert copied_template.snapshot_id != snapshot.id

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_copy_template_with_versioning(self, mock_get_config):
        """测试在版本管理模式下复制模板"""
        mock_get_config.return_value = "true"

        # 创建原始模板
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        original_template = Template.objects.create(
            name="Original Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        snapshot.template_id = original_template.id
        snapshot.save()

        # 复制模板
        copied_template = Template.objects.copy_template(
            template_id=original_template.id, space_id=self.space.id, operator="admin"
        )

        # 验证
        assert copied_template.id != original_template.id
        assert copied_template.name == "Copy Original Template"
        assert copied_template.space_id == self.space.id
        # 在版本管理模式下应该创建草稿快照
        copied_snapshot = TemplateSnapshot.objects.get(id=copied_template.snapshot_id)
        assert copied_snapshot.draft is True

    # @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    # def test_copy_template_with_subprocess(self, mock_get_config):
    #     """测试复制包含子流程的模板"""
    #     mock_get_config.return_value = "false"

    #     # 创建子流程模板
    #     sub_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
    #     sub_template = Template.objects.create(
    #         name="Sub Template",
    #         space_id=self.space.id,
    #         snapshot_id=sub_snapshot.id,
    #         creator="admin",
    #         updated_by="admin"
    #     )
    #     sub_snapshot.template_id = sub_template.id
    #     sub_snapshot.save()

    #     # 创建包含子流程的模板，使用正确的 pipeline 结构
    #     parent_tree = deepcopy(self.pipeline_tree)

    #     # 添加子流程节点
    #     subprocess_node_id = "subprocess_node"
    #     parent_tree["activities"][subprocess_node_id] = {
    #         "id": subprocess_node_id,
    #         "type": "SubProcess",
    #         "template_id": sub_template.id,
    #         "version": sub_snapshot.md5sum,
    #         "name": "subprocess",
    #         "incoming": ["flow3"],  # 从 start_event 连接
    #         "outgoing": "flow4"      # 连接到 end_event
    #     }

    #     # 添加相应的 flows
    #     parent_tree["flows"]["flow3"] = {
    #         "id": "flow3",
    #         "source": parent_tree["start_event"]["id"],
    #         "target": subprocess_node_id,
    #         "is_default": False
    #     }
    #     parent_tree["flows"]["flow4"] = {
    #         "id": "flow4",
    #         "source": subprocess_node_id,
    #         "target": parent_tree["end_event"]["id"],
    #         "is_default": False
    #     }

    #     # 更新 start_event 和 end_event 的连接
    #     parent_tree["start_event"]["outgoing"] = "flow3"
    #     parent_tree["end_event"]["incoming"] = ["flow4"]

    #     parent_snapshot = TemplateSnapshot.create_snapshot(parent_tree, "admin", "1.0.0")
    #     parent_template = Template.objects.create(
    #         name="Parent Template",
    #         space_id=self.space.id,
    #         snapshot_id=parent_snapshot.id,
    #         creator="admin",
    #         updated_by="admin"
    #     )
    #     parent_snapshot.template_id = parent_template.id
    #     parent_snapshot.save()

    #     # 复制模板（不复制子流程）
    #     copied_template = Template.objects.copy_template(
    #         template_id=parent_template.id,
    #         space_id=self.space.id,
    #         operator="admin",
    #         copy_subprocess=False
    #     )

    #     # 验证
    #     assert copied_template.id != parent_template.id
    #     assert "Copy Parent Template" in copied_template.name
    #     # 验证子流程节点被复制
    #     copied_tree = copied_template.pipeline_tree
    #     assert any(act.get("type") == "SubProcess" for act in copied_tree["activities"].values())

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_copy_template_with_dmn_plugin(self, mock_get_config):
        """测试复制包含决策节点的模板应该抛出异常"""
        mock_get_config.return_value = "false"

        # 创建包含决策节点的模板
        dmn_tree = deepcopy(self.pipeline_tree)
        dmn_tree["activities"]["dmn_node"] = {
            "id": "dmn_node",
            "type": "ServiceActivity",
            "name": "dmn_node",
            "component": {"code": "dmn_plugin"},
            "incoming": [],
            "outgoing": [],
        }

        dmn_snapshot = TemplateSnapshot.create_snapshot(dmn_tree, "admin", "1.0.0")
        dmn_template = Template.objects.create(
            name="DMN Template",
            space_id=self.space.id,
            snapshot_id=dmn_snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        dmn_snapshot.template_id = dmn_template.id
        dmn_snapshot.save()

        # 尝试复制应该抛出异常
        with pytest.raises(ValidationError, match="决策节点"):
            Template.objects.copy_template(template_id=dmn_template.id, space_id=self.space.id, operator="admin")


@pytest.mark.django_db
class TestTemplate:
    """测试 Template 模型"""

    def setup_method(self):
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_to_json(self):
        """测试 to_json 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
            desc="Test Description",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 测试包含 pipeline_tree
        json_data = template.to_json(with_pipeline_tree=True)
        assert json_data["id"] == template.id
        assert json_data["name"] == "Test Template"
        assert json_data["desc"] == "Test Description"
        assert "pipeline_tree" in json_data

        # 测试不包含 pipeline_tree
        json_data_without_tree = template.to_json(with_pipeline_tree=False)
        assert "pipeline_tree" not in json_data_without_tree

    def test_exists(self):
        """测试 exists 类方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert Template.exists(template.id) is True
        assert Template.exists(99999) is False

    def test_snapshot_property(self):
        """测试 snapshot 属性"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert template.snapshot.id == snapshot.id
        assert template.snapshot.version == "1.0.0"

    def test_pipeline_tree_property(self):
        """测试 pipeline_tree 属性"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        pipeline_tree = template.pipeline_tree
        assert pipeline_tree["id"] == "test_pipeline_id"
        assert "activities" in pipeline_tree

    def test_build_callback_data(self):
        """测试 build_callback_data 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        callback_data = template.build_callback_data("create")
        assert callback_data["type"] == "template"
        assert callback_data["data"]["id"] == template.id
        assert callback_data["data"]["operate_type"] == "create"

    def test_update_snapshot(self):
        """测试 update_snapshot 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 更新 pipeline_tree
        new_tree = deepcopy(self.pipeline_tree)
        new_tree["constants"]["${key2}"] = {"key": "key2", "value": "value2"}

        template.update_snapshot(new_tree)

        # 验证快照已更新
        updated_snapshot = TemplateSnapshot.objects.get(id=snapshot.id)
        assert "${key2}" in updated_snapshot.data["constants"]

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_get_pipeline_tree_by_version_with_versioning(self, mock_get_config):
        """测试在版本管理模式下获取指定版本的 pipeline_tree"""
        mock_get_config.return_value = "true"

        # 创建多个版本的快照
        snapshot1 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot1.id, creator="admin", updated_by="admin"
        )
        snapshot1.template_id = template.id
        snapshot1.save()

        tree2 = deepcopy(self.pipeline_tree)
        tree2["constants"]["${key2}"] = {"key": "key2", "value": "value2"}
        snapshot2 = TemplateSnapshot.create_snapshot(tree2, "admin", "2.0.0")
        snapshot2.template_id = template.id
        snapshot2.save()

        # 获取指定版本
        tree_v1 = template.get_pipeline_tree_by_version("1.0.0")
        assert "${key2}" not in tree_v1["constants"]

        tree_v2 = template.get_pipeline_tree_by_version("2.0.0")
        assert "${key2}" in tree_v2["constants"]

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_get_pipeline_tree_by_version_without_versioning(self, mock_get_config):
        """测试在非版本管理模式下使用 md5sum 获取 pipeline_tree"""
        mock_get_config.return_value = "false"

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 使用 md5sum 获取
        md5sum = snapshot.md5sum
        tree = template.get_pipeline_tree_by_version(md5sum)
        assert tree["id"] == "test_pipeline_id"

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_get_pipeline_tree_by_version_not_found(self, mock_get_config):
        """测试获取不存在的版本应该抛出异常"""
        mock_get_config.return_value = "true"

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        with pytest.raises(ValidationError, match="not found"):
            template.get_pipeline_tree_by_version("999.0.0")

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_version_property_with_versioning(self, mock_get_config):
        """测试在版本管理模式下的 version 属性"""
        mock_get_config.return_value = "true"

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert template.version == "1.0.0"

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_version_property_without_versioning(self, mock_get_config):
        """测试在非版本管理模式下的 version 属性返回 md5sum"""
        mock_get_config.return_value = "false"

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert template.version == snapshot.md5sum

    def test_snapshot_version_property(self):
        """测试 snapshot_version 属性"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert template.snapshot_version == "1.0.0"

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_validate_space(self, mock_get_config):
        """测试 validate_space 方法"""
        mock_get_config.return_value = "true"

        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        assert template.validate_space("true") is True
        assert template.validate_space("false") is False

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_subprocess_info_with_versioning(self, mock_get_config):
        """测试在版本管理模式下的 subprocess_info 属性"""
        mock_get_config.return_value = "true"

        # 创建子流程模板
        sub_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        sub_template = Template.objects.create(
            name="Sub Template",
            space_id=self.space.id,
            snapshot_id=sub_snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        sub_snapshot.template_id = sub_template.id
        sub_snapshot.save()

        # 创建主流程模板
        main_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        main_template = Template.objects.create(
            name="Main Template",
            space_id=self.space.id,
            snapshot_id=main_snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        main_snapshot.template_id = main_template.id
        main_snapshot.save()

        # 创建引用关系（使用 md5sum）
        TemplateReference.objects.create(
            root_template_id=str(main_template.id),
            subprocess_template_id=str(sub_template.id),
            subprocess_node_id="subprocess_node_1",
            version=sub_snapshot.md5sum,
            always_use_latest=False,
        )

        # 获取子流程信息
        info = main_template.subprocess_info
        assert len(info) == 1
        assert info[0]["subprocess_template_id"] == str(sub_template.id)
        assert info[0]["subprocess_template_name"] == "Sub Template"

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_subprocess_info_always_use_latest(self, mock_get_config):
        """测试永远使用最新版本的子流程"""
        mock_get_config.return_value = "true"

        # 创建子流程模板
        sub_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        sub_template = Template.objects.create(
            name="Sub Template",
            space_id=self.space.id,
            snapshot_id=sub_snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        sub_snapshot.template_id = sub_template.id
        sub_snapshot.save()

        # 创建主流程模板
        main_snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        main_template = Template.objects.create(
            name="Main Template",
            space_id=self.space.id,
            snapshot_id=main_snapshot.id,
            creator="admin",
            updated_by="admin",
        )
        main_snapshot.template_id = main_template.id
        main_snapshot.save()

        # 创建引用关系，设置永远使用最新版本
        TemplateReference.objects.create(
            root_template_id=str(main_template.id),
            subprocess_template_id=str(sub_template.id),
            subprocess_node_id="subprocess_node_1",
            version="1.0.0",
            always_use_latest=True,
        )

        # 获取子流程信息
        info = main_template.subprocess_info
        assert len(info) == 1
        assert info[0]["expired"] is False  # 永远使用最新版本，不会过期

    def test_outputs(self):
        """测试 outputs 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        outputs = template.outputs()
        assert "${key1}" in outputs
        assert outputs["${key1}"]["key"] == "key1"

    @mock.patch("bkflow.template.models.SpaceConfig.get_config")
    def test_outputs_with_version(self, mock_get_config):
        """测试指定版本的 outputs 方法"""
        # Mock为版本管理模式
        mock_get_config.return_value = "true"

        # 创建第一个版本
        snapshot1 = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot1.id, creator="admin", updated_by="admin"
        )
        snapshot1.template_id = template.id
        snapshot1.save()

        # 创建第二个版本，添加新的输出
        tree2 = deepcopy(self.pipeline_tree)
        tree2["constants"]["${key2}"] = {"key": "key2", "value": "value2"}
        tree2["outputs"].append("${key2}")
        snapshot2 = TemplateSnapshot.create_snapshot(tree2, "admin", "2.0.0")
        snapshot2.template_id = template.id
        snapshot2.save()

        # 获取不同版本的输出
        outputs_v1 = template.outputs("1.0.0")
        assert "${key1}" in outputs_v1
        assert "${key2}" not in outputs_v1

        outputs_v2 = template.outputs("2.0.0")
        assert "${key1}" in outputs_v2
        assert "${key2}" in outputs_v2

    def test_update_draft_snapshot(self):
        """测试 update_draft_snapshot 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 更新草稿快照
        new_tree = deepcopy(self.pipeline_tree)
        new_tree["constants"]["${draft_key}"] = {"key": "draft_key", "value": "draft_value"}

        draft_snapshot = template.update_draft_snapshot(new_tree, "test_user", version="1.0.0")

        assert draft_snapshot.draft is True
        assert draft_snapshot.template_id == template.id
        assert "${draft_key}" in draft_snapshot.data["constants"]
        assert "基于 1.0.0 版本的草稿" in draft_snapshot.desc

    def test_update_draft_snapshot_existing_draft(self):
        """测试更新已存在的草稿快照"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 第一次创建草稿
        new_tree1 = deepcopy(self.pipeline_tree)
        draft_snapshot1 = template.update_draft_snapshot(new_tree1, "test_user")
        draft_id1 = draft_snapshot1.id

        # 第二次更新草稿（应该更新同一个草稿）
        new_tree2 = deepcopy(self.pipeline_tree)
        new_tree2["constants"]["${updated_key}"] = {"key": "updated_key", "value": "updated_value"}
        draft_snapshot2 = template.update_draft_snapshot(new_tree2, "test_user2")

        assert draft_snapshot2.id == draft_id1  # 应该是同一个草稿
        assert "${updated_key}" in draft_snapshot2.data["constants"]
        assert draft_snapshot2.operator == "test_user2"

    def test_release_template(self):
        """测试 release_template 方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建草稿
        draft_tree = deepcopy(self.pipeline_tree)
        template.update_draft_snapshot(draft_tree, "test_user")

        # 发布模板
        released_snapshot = template.release_template(
            {"version": "2.0.0", "desc": "Release description", "username": "test_user"}
        )

        assert released_snapshot.draft is False
        assert released_snapshot.version == "2.0.0"
        assert released_snapshot.desc == "Release description"
        assert released_snapshot.operator == "test_user"

    def test_release_template_no_version(self):
        """测试发布模板时没有提供版本号"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        with pytest.raises(ValidationError, match="版本号不能为空"):
            template.release_template({"username": "test_user"})

    def test_release_template_no_draft(self):
        """测试发布模板时没有草稿"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        with pytest.raises(ValidationError, match="没有草稿版本"):
            template.release_template({"version": "2.0.0", "username": "test_user"})


@pytest.mark.django_db
class TestTemplateSnapshot:
    """测试 TemplateSnapshot 模型"""

    def setup_method(self):
        self.pipeline_tree = build_pipeline_tree()

    def test_create_snapshot(self):
        """测试 create_snapshot 类方法"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")

        assert snapshot.version == "1.0.0"
        assert snapshot.creator == "admin"
        assert snapshot.operator == "admin"
        assert snapshot.draft is False
        assert snapshot.data == self.pipeline_tree

    def test_create_draft_snapshot_with_version(self):
        """测试创建带版本号的草稿快照"""
        snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "admin", version="1.0.0")

        assert snapshot.version == "1.0.0"
        assert snapshot.creator == "admin"
        assert snapshot.draft is False  # 有版本号时不是草稿

    def test_create_draft_snapshot_without_version(self):
        """测试创建不带版本号的草稿快照"""
        snapshot = TemplateSnapshot.create_draft_snapshot(self.pipeline_tree, "admin")

        assert snapshot.creator == "admin"
        assert snapshot.draft is True  # 无版本号时是草稿


@pytest.mark.django_db
class TestTemplateMockDataManager:
    """测试 TemplateMockDataManager"""

    def setup_method(self):
        self.space = Space.objects.create(name="Test Space", app_code="test_app")
        self.pipeline_tree = build_pipeline_tree()

    def test_batch_create(self):
        """测试批量创建 Mock 数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        mock_data = {
            "node1": [
                {"name": "mock1", "data": {"key": "value1"}, "is_default": True},
                {"name": "mock2", "data": {"key": "value2"}, "is_default": False},
            ],
            "node2": [{"name": "mock3", "data": {"key": "value3"}, "is_default": True}],
        }

        result = TemplateMockData.objects.batch_create(
            operator="test_user", space_id=self.space.id, template_id=template.id, mock_data=mock_data
        )

        assert result.count() == 3
        assert TemplateMockData.objects.filter(node_id="node1").count() == 2
        assert TemplateMockData.objects.filter(node_id="node2").count() == 1

    def test_batch_update(self):
        """测试批量更新 Mock 数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建初始数据
        existing_mock = TemplateMockData.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            node_id="node1",
            name="old_mock",
            data={"key": "old_value"},
            is_default=True,
            operator="admin",
        )

        # 批量更新
        mock_data = {
            "node1": [
                {"id": existing_mock.id, "name": "updated_mock", "data": {"key": "updated_value"}, "is_default": False},
                {"name": "new_mock", "data": {"key": "new_value"}, "is_default": True},
            ]
        }

        result = TemplateMockData.objects.batch_update(
            operator="test_user", space_id=self.space.id, template_id=template.id, mock_data=mock_data
        )

        # 验证更新
        updated_mock = TemplateMockData.objects.get(id=existing_mock.id)
        assert updated_mock.name == "updated_mock"
        assert updated_mock.data == {"key": "updated_value"}
        assert updated_mock.is_default is False
        assert updated_mock.operator == "test_user"

        # 验证新增
        assert result.count() == 2

    def test_batch_update_with_delete(self):
        """测试批量更新时删除不在列表中的数据"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建初始数据
        mock1 = TemplateMockData.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            node_id="node1",
            name="mock1",
            data={"key": "value1"},
            is_default=True,
            operator="admin",
        )

        mock2 = TemplateMockData.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            node_id="node1",
            name="mock2",
            data={"key": "value2"},
            is_default=False,
            operator="admin",
        )

        # 批量更新，只保留 mock1
        mock_data = {
            "node1": [{"id": mock1.id, "name": "updated_mock1", "data": {"key": "updated_value1"}, "is_default": True}]
        }

        result = TemplateMockData.objects.batch_update(
            operator="test_user", space_id=self.space.id, template_id=template.id, mock_data=mock_data
        )

        # 验证 mock2 被删除
        assert result.count() == 1
        assert not TemplateMockData.objects.filter(id=mock2.id).exists()


@pytest.mark.django_db
class TestTriggerManager:
    """测试 TriggerManager"""

    def setup_method(self):
        from bkflow.admin.models import ModuleInfo

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

    @mock.patch("bkflow.template.models.TaskComponentClient")
    def test_create_trigger(self, mock_client_class):
        """测试创建触发器"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
            scope_type="project",
            scope_value="123",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # Mock API 调用
        mock_client = mock.Mock()
        mock_client.create_periodic_task.return_value = {"result": True}
        mock_client_class.return_value = mock_client

        # 创建触发器
        trigger_data = {
            "space_id": self.space.id,
            "template_id": template.id,
            "name": "Test Trigger",
            "type": Trigger.TYPE_PERIODIC,
            "is_enabled": True,
            "config": {"cron": {"minute": "0", "hour": "*", "day": "*", "month": "*", "week": "*"}, "constants": {}},
            "creator": "admin",
        }

        trigger = Trigger.objects.create_trigger(trigger_data, template)

        assert trigger.name == "Test Trigger"
        assert trigger.template_id == template.id
        mock_client.create_periodic_task.assert_called_once()

    @mock.patch("bkflow.template.models.TaskComponentClient")
    def test_update_trigger(self, mock_client_class):
        """测试更新触发器"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
            scope_type="project",
            scope_value="123",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建触发器
        trigger = Trigger.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            name="Test Trigger",
            type=Trigger.TYPE_PERIODIC,
            is_enabled=True,
            config={"cron": {"minute": "0", "hour": "*", "day": "*", "month": "*", "week": "*"}, "constants": {}},
            creator="admin",
        )

        # Mock API 调用
        mock_client = mock.Mock()
        mock_client.update_periodic_task.return_value = {"result": True}
        mock_client_class.return_value = mock_client

        # 更新触发器
        update_data = {
            "name": "Updated Trigger",
            "config": {"cron": {"minute": "30", "hour": "*", "day": "*", "month": "*", "week": "*"}, "constants": {}},
            "is_enabled": False,
        }

        updated_trigger = Trigger.objects.update_trigger(trigger, update_data, template)

        assert updated_trigger.name == "Updated Trigger"
        assert updated_trigger.is_enabled is False
        mock_client.update_periodic_task.assert_called_once()

    @mock.patch("bkflow.template.models.TaskComponentClient")
    def test_batch_delete_by_ids(self, mock_client_class):
        """测试批量删除触发器"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template", space_id=self.space.id, snapshot_id=snapshot.id, creator="admin", updated_by="admin"
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建触发器
        trigger1 = Trigger.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            name="Trigger 1",
            type=Trigger.TYPE_PERIODIC,
            config={},
            creator="admin",
        )

        trigger2 = Trigger.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            name="Trigger 2",
            type=Trigger.TYPE_PERIODIC,
            config={},
            creator="admin",
        )

        # Mock API 调用
        mock_client = mock.Mock()
        mock_client.batch_delete_periodic_task.return_value = {"result": True}
        mock_client_class.return_value = mock_client

        # 批量删除
        Trigger.objects.batch_delete_by_ids(self.space.id, [trigger1.id, trigger2.id])

        # 验证删除
        assert not Trigger.objects.filter(id=trigger1.id).exists()
        assert not Trigger.objects.filter(id=trigger2.id).exists()

    def test_compare_constants(self):
        """测试比较常量"""
        pre_constants = {"${key1}": {"show_type": "show"}, "${key2}": {"show_type": "hide"}}

        input_constants = {"${key1}": {"show_type": "show"}, "${key3}": {"show_type": "show"}}

        triggers = [
            {
                "config": {
                    "constants": {"${key1}": "value1"},
                    "cron": {"minute": "0", "hour": "*", "day": "*", "month": "*", "week": "*"},
                }
            }
        ]

        # 应该抛出异常，因为 ${key3} 是新增的但触发器中没有
        with pytest.raises(ValidationError, match="新增参数未填写"):
            Trigger.objects.compare_constants(pre_constants, input_constants, triggers)

    @mock.patch("bkflow.template.models.TaskComponentClient")
    def test_batch_modify_triggers(self, mock_client_class):
        """测试批量修改触发器"""
        snapshot = TemplateSnapshot.create_snapshot(self.pipeline_tree, "admin", "1.0.0")
        template = Template.objects.create(
            name="Test Template",
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="admin",
            updated_by="admin",
            scope_type="project",
            scope_value="123",
        )
        snapshot.template_id = template.id
        snapshot.save()

        # 创建现有触发器
        existing_trigger = Trigger.objects.create(
            space_id=self.space.id,
            template_id=template.id,
            name="Existing Trigger",
            type=Trigger.TYPE_PERIODIC,
            config={"cron": {"minute": "0", "hour": "*", "day": "*", "month": "*", "week": "*"}, "constants": {}},
            creator="admin",
        )

        # Mock API 调用
        mock_client = mock.Mock()
        mock_client.create_periodic_task.return_value = {"result": True}
        mock_client.update_periodic_task.return_value = {"result": True}
        mock_client.batch_delete_periodic_task.return_value = {"result": True}
        mock_client_class.return_value = mock_client

        # 批量修改（更新、创建、删除）
        triggers_data = [
            {
                "id": existing_trigger.id,
                "space_id": self.space.id,
                "template_id": template.id,
                "name": "Updated Trigger",
                "type": Trigger.TYPE_PERIODIC,
                "config": {
                    "cron": {"minute": "30", "hour": "*", "day": "*", "month": "*", "week": "*"},
                    "constants": {},
                },
                "is_enabled": True,
            },
            {
                "space_id": self.space.id,
                "template_id": template.id,
                "name": "New Trigger",
                "type": Trigger.TYPE_PERIODIC,
                "config": {
                    "cron": {"minute": "15", "hour": "*", "day": "*", "month": "*", "week": "*"},
                    "constants": {},
                },
                "is_enabled": True,
                "creator": "admin",
            },
        ]

        Trigger.objects.batch_modify_triggers(template, triggers_data)

        # 验证更新
        updated = Trigger.objects.get(id=existing_trigger.id)
        assert updated.name == "Updated Trigger"

        # 验证新增
        new_trigger = Trigger.objects.filter(name="New Trigger").first()
        assert new_trigger is not None
