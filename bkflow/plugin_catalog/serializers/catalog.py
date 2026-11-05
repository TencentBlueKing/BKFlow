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

from bkflow.plugin_catalog.models import PluginCatalogStatus


class _MultiValueCharField(serializers.CharField):
    """支持 `a,b,c` 或重复 query 参数两种多值写法，统一解析成 list[str]。"""

    def to_internal_value(self, data):
        if isinstance(data, (list, tuple)):
            values = data
        else:
            values = str(data).split(",")
        return [v.strip() for v in values if v and v.strip()]


class SpaceIdQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class EntryListQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.CharField(
        help_text=_("all/recommend/uncategorized/具体目录id"), required=False, default="all"
    )
    status = _MultiValueCharField(help_text=_("all(默认,不含invalid)/六态任意组合"), required=False, default=list)
    plugin_type = _MultiValueCharField(required=False, default=list)
    source_key = _MultiValueCharField(required=False, default=list)
    keyword = _MultiValueCharField(help_text=_("模糊匹配插件名称或最近修改人，OR 语义"), required=False, default=list)
    ordering = serializers.ChoiceField(
        choices=["-update_at", "update_at", "-ref_count", "ref_count", "name", "-name"],
        required=False,
        default="-update_at",
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)


class EntryUpdateSerializer(serializers.Serializer):
    """01 · 编辑单条（目录 + 推荐），两个字段均为可选，只提交的字段才会被改写。"""

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    recommended = serializers.BooleanField(required=False)


class EntryStatusSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    status = serializers.ChoiceField(
        choices=[s for s, _label in PluginCatalogStatus.CHOICES if s != PluginCatalogStatus.INVALID]
    )
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    disable_config = serializers.DictField(required=False)
    offline_reason = serializers.CharField(required=False, allow_blank=True, default="")
    replace_plugin_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["status"] == PluginCatalogStatus.VISIBLE and "target_directory_id" not in self.initial_data:
            raise serializers.ValidationError("启用插件需要指定 target_directory_id（可为空表示未分类）")
        return attrs


class SuggestDirectoryQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class PluginDetailQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class ReferenceListQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    scope = serializers.ChoiceField(choices=["all", "published", "draft"], required=False, default="all")
    keyword = serializers.CharField(required=False, allow_blank=True, default="")
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=200)


class DisableConfigSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    disable_config = serializers.DictField(help_text=_("停用提示文案/联系方式等自定义内容"))


class BatchCategorySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class BatchStatusItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class BatchStatusSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    status = serializers.ChoiceField(
        choices=[s for s, _label in PluginCatalogStatus.CHOICES if s != PluginCatalogStatus.INVALID]
    )
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    items = BatchStatusItemSerializer(many=True, required=False, default=list)


class BatchCleanSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
