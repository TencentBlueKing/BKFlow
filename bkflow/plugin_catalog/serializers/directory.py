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

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkflow.plugin_catalog.services.directory_service import DirectoryService


class SpaceIdQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class ManageSaveSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    expected_revision = serializers.IntegerField(help_text=_("GET manage_data 时返回的版本号"))
    directories = serializers.DictField(
        help_text=_("目录文档，key 为前端本地/真实目录 id"), required=False, default=dict
    )
    assignments = serializers.DictField(
        help_text=_("插件归属变更，key 为插件条目 id，value 为目录 id（空串=未分类）"),
        required=False,
        default=dict,
    )

    def validate_directories(self, value):
        """校验整页提交的目录文档。

        `order` 是**必填**的：它是同级目录之间的排序号（升序，越小越靠前），
        由前端在拖拽后按新顺序给出。若不传，后端会退化成"全部为 0 → 按 id 排"，
        表现为"拖了没生效"却没有任何报错，属于静默失败，所以这里直接拦掉。

        同一 `parent_id` 下的 `order` 必须唯一，否则同级排序在重复值处退化成按 id 排，
        前端拿到的顺序与预期不一致，同样要显式报错。
        """
        for key, item in value.items():
            if not isinstance(item, dict) or not item.get("name"):
                raise serializers.ValidationError(f"目录 {key} 缺少必填字段 name")
            if "order" not in item:
                raise serializers.ValidationError(f"目录 {key} 缺少必填字段 order")
            if isinstance(item["order"], bool) or not isinstance(item["order"], int):
                raise serializers.ValidationError(f"目录 {key} 的 order 必须是整数")

        seen = {}
        for key, item in value.items():
            parent_id = (item.get("parent_id") or "").strip()
            order = item["order"]
            signature = (parent_id, order)
            if signature in seen:
                raise serializers.ValidationError(
                    f"目录 {key} 与目录 {seen[signature]} 的 order 重复（同级的 order 必须唯一）"
                )
            seen[signature] = key
        return value


class _CommaSeparatedIdsField(serializers.CharField):
    """目录 id 列表：**逗号分隔**，如 `"12,15,18"`。"""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        ids = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if not part.lstrip("-").isdigit():
                raise serializers.ValidationError(f"目录 id {part} 不是合法的整数")
            ids.append(int(part))
        if not ids:
            raise serializers.ValidationError("至少要传一个目录 id")
        # 去重但保持顺序
        return list(dict.fromkeys(ids))


class PreviewDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_ids = _CommaSeparatedIdsField(help_text=_("待删除目录 id 列表，逗号分隔，如 12,15,18"))


class ExecuteDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_ids = _CommaSeparatedIdsField(help_text=_("待删除目录 id 列表，逗号分隔，如 12,15,18"))


class AiClassifySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    scope = serializers.ChoiceField(choices=["free", "selected"], default="free", help_text=_("free=全部未分类；selected=指定插件"))
    plugin_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list, help_text=_("scope=selected 时必填")
    )
