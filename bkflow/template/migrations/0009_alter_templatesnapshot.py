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

import logging

from django.db import migrations

from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.utils.version import bump_custom

logger = logging.getLogger(__name__)


def add_version_to_snapshots(apps, schema_editor):
    """
    为未开启版本管理的空间下的模板快照添加版本号
    版本号从1.0.0开始，按创建时间依次递增
    """
    disabled_versioning_spaces = []
    all_space_configs = SpaceConfig.objects.filter(name=FlowVersioning.name)

    for config in all_space_configs:
        if config.value_type == "TEXT":
            value = config.text_value
        elif config.value_type == "JSON":
            value = config.json_value.get("value", "false") if config.json_value else "false"
        else:
            value = "false"

        if value == "false":
            disabled_versioning_spaces.append(config.space_id)

    # 如果没有配置记录的空间，也认为是未开启版本管理
    all_spaces_with_templates = Template.objects.values_list("space_id", flat=True).distinct()
    spaces_without_config = set(all_spaces_with_templates) - {c.space_id for c in all_space_configs}
    disabled_versioning_spaces.extend(list(spaces_without_config))

    disabled_versioning_spaces = list(set(disabled_versioning_spaces))

    logger.info(f"找到 {len(disabled_versioning_spaces)} 个未开启版本管理的空间")
    # 记录本次迁移修改的快照ID，用于精确回滚
    modified_snapshot_ids = []
    snapshots_to_update = []

    template_ids = Template.objects.filter(space_id__in=disabled_versioning_spaces, is_deleted=False).values_list(
        "id", flat=True
    )

    if not template_ids:
        logger.info("没有需要处理的模板")
        return

    # 批量获取所有快照，按模板ID分组
    all_snapshots = TemplateSnapshot.objects.filter(template_id__in=template_ids).order_by("template_id", "create_time")
    snapshots_by_template = {}
    for snapshot in all_snapshots:
        if snapshot.template_id not in snapshots_by_template:
            snapshots_by_template[snapshot.template_id] = []
        snapshots_by_template[snapshot.template_id].append(snapshot)

    # 获取所有模板信息
    templates_by_id = {t.id: t for t in Template.objects.filter(id__in=template_ids)}

    # 处理每个模板
    for template_id in template_ids:
        template = templates_by_id.get(template_id)
        if not template:
            continue

        snapshots = snapshots_by_template.get(template_id, [])

        current_version = "1.0.0"
        for index, snapshot in enumerate(snapshots):
            if getattr(snapshot, "draft", None):
                continue
            snapshot.version = current_version
            snapshot.draft = False

            snapshots_to_update.append(snapshot)
            modified_snapshot_ids.append(snapshot.id)
            current_version = bump_custom(current_version)

        logger.info(f"模板 {template.id} 的 {len(snapshots)} 个快照已分配版本号")

    TemplateSnapshot.objects.bulk_update(snapshots_to_update, ["version", "draft"])

    # 将修改的快照ID保存到schema_editor的connection中，用于回滚
    if hasattr(schema_editor.connection, "migration_data"):
        schema_editor.connection.migration_data = {"modified_snapshot_ids": modified_snapshot_ids}
    logger.info(f"本次迁移共修改了 {len(modified_snapshot_ids)} 个快照")


def reverse_add_version_to_snapshots(apps, schema_editor):
    """回滚操作：只清除本次迁移修改的快照的版本号"""
    # 尝试获取本次迁移修改的快照ID
    modified_snapshot_ids = []
    if hasattr(schema_editor.connection, "migration_data"):
        migration_data = getattr(schema_editor.connection, "migration_data", {})
        modified_snapshot_ids = migration_data.get("modified_snapshot_ids", [])

    if modified_snapshot_ids:
        TemplateSnapshot.objects.filter(id__in=modified_snapshot_ids).update(version=None)
        logger.info(f"回滚操作：清除了 {len(modified_snapshot_ids)} 个快照的版本号")
    else:
        logger.info("回滚操作：未找到本次迁移修改的快照ID")


class Migration(migrations.Migration):
    dependencies = [
        ("template", "0008_alter_templatesnapshot_version"),
    ]

    operations = [
        migrations.RunPython(add_version_to_snapshots, reverse_add_version_to_snapshots),
    ]
