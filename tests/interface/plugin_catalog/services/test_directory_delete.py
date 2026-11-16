"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (see LICENSE for details).
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import pytest

from bkflow.exceptions import ValidationError
from bkflow.plugin_catalog.models import (
    PluginCatalogStatus,
    PluginDirectory,
    PluginType,
    SpacePluginCatalogEntry,
)
from bkflow.plugin_catalog.services.directory_service import DirectoryService

SPACE_ID = 1


def make_directory(name, parent=None, order=1):
    return PluginDirectory.objects.create(space_id=SPACE_ID, parent=parent, name=name, order=order)


def make_entry(plugin_code, directory=None):
    return SpacePluginCatalogEntry.objects.create(
        space_id=SPACE_ID,
        plugin_type=PluginType.BUILTIN,
        source_key="",
        plugin_code=plugin_code,
        plugin_name=plugin_code,
        plugin_desc="",
        directory_id=directory.id if directory else None,
        status=PluginCatalogStatus.ENABLE,
        ever_enabled=True,
        updated_by="tester",
    )


@pytest.mark.django_db
class TestPreviewDelete:
    """删除预览：设计稿确认弹窗需要的信息，支持批量。"""

    def test_preview_returns_design_fields(self):
        top = make_directory("通用能力", order=1)
        child = make_directory("流程控制", parent=top, order=1)
        make_entry("p_direct", directory=top)
        make_entry("p_in_child", directory=child)

        preview = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[top.id])

        assert preview["total"] == 1
        item = preview["items"][0]
        assert item["name"] == "通用能力"
        assert item["level"] == 1
        assert item["children_count"] == 1
        assert item["children_effect"] == "变成一级目录"
        # 只算直接挂在本目录的插件：子目录里的插件跟着子目录走，不受影响
        assert item["plugin_count"] == 1
        assert item["plugin_effect"] == "移入「未分类插件」"
        assert item["conflicts"] == []
        assert preview["total_children_count"] == 1
        assert preview["total_plugin_count"] == 1
        assert preview["conflicts"] == []

    def test_preview_second_level_has_no_children(self):
        top = make_directory("通用能力", order=1)
        child = make_directory("流程控制", parent=top, order=1)

        item = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[child.id])["items"][0]

        assert item["level"] == 2
        assert item["children_count"] == 0
        assert item["children_effect"] == "无影响"
        assert item["plugin_count"] == 0
        assert item["plugin_effect"] == "无影响"

    def test_preview_reports_conflicts_with_existing(self):
        top = make_directory("通用能力", order=1)
        make_directory("流程控制", parent=top, order=1)
        make_directory("流程控制", order=2)  # 已存在同名一级目录

        preview = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[top.id])

        assert preview["conflicts"] == ["流程控制"]
        assert preview["items"][0]["conflicts"] == ["流程控制"]

    def test_preview_supports_batch(self):
        top_a = make_directory("A", order=1)
        top_b = make_directory("B", order=2)
        make_directory("A子", parent=top_a, order=1)
        make_entry("p_a", directory=top_a)
        make_entry("p_b", directory=top_b)

        preview = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[top_a.id, top_b.id])

        assert preview["total"] == 2
        assert [item["name"] for item in preview["items"]] == ["A", "B"]
        assert preview["total_children_count"] == 1
        assert preview["total_plugin_count"] == 2

    def test_preview_detects_conflict_between_two_children(self):
        """A 的子目录与 B 的子目录同名 -> 批量提升后互相撞名。"""
        top_a = make_directory("A", order=1)
        top_b = make_directory("B", order=2)
        make_directory("同名子目录", parent=top_a, order=1)
        make_directory("同名子目录", parent=top_b, order=1)

        preview = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[top_a.id, top_b.id])

        assert preview["conflicts"] == ["同名子目录"]

    def test_preview_ignores_children_also_being_deleted(self):
        """同时删父目录和它的子目录：子目录直接被删，不需要提升，也不该报冲突。"""
        top = make_directory("A", order=1)
        child = make_directory("同名", parent=top, order=1)
        make_directory("同名", order=2)  # 已存在同名一级目录

        preview = DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[top.id, child.id])

        assert preview["conflicts"] == []
        assert preview["total_children_count"] == 0

    def test_preview_rejects_missing_directory(self):
        with pytest.raises(ValidationError):
            DirectoryService.preview_delete(space_id=SPACE_ID, directory_ids=[999999])


@pytest.mark.django_db
class TestExecuteDelete:
    """删除只有一套行为（开发文档 04 L18）：子目录提升、直接插件移未分类。"""

    def test_delete_promotes_children_and_moves_direct_plugins(self):
        top = make_directory("通用能力", order=1)
        child = make_directory("流程控制", parent=top, order=1)
        direct = make_entry("p_direct", directory=top)
        in_child = make_entry("p_in_child", directory=child)

        result = DirectoryService.execute_delete(space_id=SPACE_ID, directory_ids=[top.id], operator="tester")

        assert result["deleted"] == 1
        assert result["promoted"] == 1
        assert result["uncategorized"] == 1
        assert not PluginDirectory.objects.filter(id=top.id).exists()
        child.refresh_from_db()
        assert child.parent_id is None  # 子目录提升为一级目录
        direct.refresh_from_db()
        assert direct.directory_id is None  # 直挂插件移入未分类
        in_child.refresh_from_db()
        assert in_child.directory_id == child.id  # 子目录里的插件跟着

    def test_delete_supports_batch(self):
        top_a = make_directory("A", order=1)
        top_b = make_directory("B", order=2)
        child = make_directory("A子", parent=top_a, order=1)
        entry_a = make_entry("p_a", directory=top_a)
        entry_b = make_entry("p_b", directory=top_b)

        result = DirectoryService.execute_delete(
            space_id=SPACE_ID, directory_ids=[top_a.id, top_b.id], operator="tester"
        )

        assert result["deleted"] == 2
        assert result["promoted"] == 1
        assert result["uncategorized"] == 2
        assert not PluginDirectory.objects.filter(id__in=[top_a.id, top_b.id]).exists()
        child.refresh_from_db()
        assert child.parent_id is None
        entry_a.refresh_from_db()
        entry_b.refresh_from_db()
        assert entry_a.directory_id is None
        assert entry_b.directory_id is None

    def test_delete_rejects_when_name_conflicts(self):
        """提升后会与已有的一级目录重名 -> 拒绝删除，让管理员先改名。"""
        top = make_directory("通用能力", order=1)
        make_directory("流程控制", parent=top, order=1)
        make_directory("流程控制", order=2)  # 已存在同名一级目录

        with pytest.raises(ValidationError) as exc_info:
            DirectoryService.execute_delete(space_id=SPACE_ID, directory_ids=[top.id], operator="tester")

        assert "重名" in str(exc_info.value)
        assert PluginDirectory.objects.filter(id=top.id).exists()  # 没有删掉

    def test_delete_rejects_whole_batch_when_any_conflicts(self):
        """批量里有一个冲突 -> 整批拒绝，不做部分删除。"""
        top_a = make_directory("A", order=1)
        top_b = make_directory("B", order=2)
        make_directory("同名子目录", parent=top_a, order=1)
        make_directory("同名子目录", parent=top_b, order=1)

        with pytest.raises(ValidationError):
            DirectoryService.execute_delete(
                space_id=SPACE_ID, directory_ids=[top_a.id, top_b.id], operator="tester"
            )

        assert PluginDirectory.objects.filter(id__in=[top_a.id, top_b.id]).count() == 2
