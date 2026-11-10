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
    deleted_plugin_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text=_("本次整理中移除的插件条目 id（软删除）"),
        required=False,
        default=list,
    )

    def validate_directories(self, value):
        for key, item in value.items():
            if not isinstance(item, dict) or not item.get("name"):
                raise serializers.ValidationError(f"目录 {key} 缺少必填字段 name")
        return value


class PreviewDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.IntegerField(help_text=_("目录ID"))


class ExecuteDeleteSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.IntegerField(help_text=_("目录ID"))
    strategy = serializers.ChoiceField(
        choices=[
            DirectoryService.STRATEGY_PROMOTE,
            DirectoryService.STRATEGY_MERGE,
            DirectoryService.STRATEGY_UNCATEGORIZED,
        ],
        required=False,
        allow_null=True,
        help_text=_("仅一级目录需要：promote(子目录升级)/merge(并入其他一级目录)/uncategorized(全部回到未分类)"),
    )
    target_directory_id = serializers.IntegerField(
        help_text=_("策略为 merge 时必填，合并到的目标一级目录 id"), required=False, allow_null=True
    )


class AiClassifySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    scope = serializers.ChoiceField(choices=["free", "selected"], default="free", help_text=_("free=全部未分类；selected=指定插件"))
    plugin_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list, help_text=_("scope=selected 时必填")
    )
