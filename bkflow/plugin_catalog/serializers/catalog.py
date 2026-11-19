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

from bkflow.plugin_catalog.models import PluginCatalogStatus, PluginType


class _CommaSeparatedListMixin:
    """多值参数：**只支持逗号分隔**，如 `?status=enable,disabled`。

    不兼容旧的「重复传参」写法（`?status=enable&status=disabled`）：DRF 取参数用
    `QueryDict.get()`，同名参数只取最后一个，重复传参时前一个值会静默丢失，
    与其让人踩坑，不如只支持一种明确的写法。
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [data]
        if isinstance(data, list):
            items = []
            for item in data:
                if isinstance(item, str):
                    items.extend([part.strip() for part in item.split(",") if part.strip()])
                else:
                    items.append(item)
            data = items
        return super().to_internal_value(data)


class _MultiChoiceField(_CommaSeparatedListMixin, serializers.ListField):
    """多选枚举：逐项校验取值合法性，并保持前端传参顺序。

    DRF 的 `MultipleChoiceField` 内部用 `set` 去重、返回顺序不保证（同样的
    `builtin,api` 两次解析可能得到不同顺序）。这里改用
    `ListField(child=ChoiceField(...))` 等价实现：校验规则一致，但顺序稳定。
    """

    def __init__(self, choices, **kwargs):
        kwargs.setdefault("child", serializers.ChoiceField(choices=choices))
        super().__init__(**kwargs)


class _StringListField(_CommaSeparatedListMixin, serializers.ListField):
    """多值字符串列表（来源 / 关键词等无固定枚举的筛选项）。"""


class SpaceIdQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class EntryListQuerySerializer(serializers.Serializer):
    """插件列表查询参数。

    **数组型参数统一用「逗号分隔」**：`?status=enable,disabled`。
    不支持重复传参（`?status=enable&status=disabled`）、方括号（`?status[]=...`）、
    JSON 字符串（`?status=["enable"]`）—— 这三种都会被当成单个字面量，导致查不到数据。
    前端用 axios 时需配 `paramsSerializer: { indexes: null }`，否则 axios 默认
    序列化成 `status[]=...`，参数会整体丢失。
    """

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.CharField(
        help_text=_("目录筛选：all(全部) / recommend(空间推荐) / uncategorized(未分类) / 具体目录 id"),
        required=False,
        default="all",
    )
    status = _MultiChoiceField(
        choices=[status for status, _label in PluginCatalogStatus.CHOICES] + ["all"],
        required=False,
        default=list,
        help_text=_("状态筛选，多值用逗号分隔；不传或传 all = 全部。all 不能与其他值混传"),
    )
    plugin_type = _MultiChoiceField(
        choices=[plugin_type for plugin_type, _label in PluginType.CHOICES],
        required=False,
        default=list,
        help_text=_("插件类型筛选，多值用逗号分隔；多值 OR"),
    )
    source_key = _StringListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text=_("来源筛选，多值用逗号分隔；多值 OR。取值同接口 12 的来源 id"),
    )
    keyword = _StringListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text=_("关键词筛选，多值用逗号分隔；多值 OR，匹配插件名称或最近修改人"),
    )
    ordering = serializers.ChoiceField(
        choices=["-update_at", "update_at", "-ref_count", "ref_count", "name", "-name"],
        required=False,
        default="-update_at",
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)

    def validate_status(self, value):
        # `all` 表示"全部"，不能与其他状态混传（混传语义无意义且容易误用）
        if "all" in value and len(value) > 1:
            raise serializers.ValidationError("status=all 不能与其他状态同时传入")
        return value


class EntryUpdateSerializer(serializers.Serializer):
    """01 · 编辑单条（目录 + 推荐），两个字段均为可选，只提交的字段才会被改写。"""

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    recommended = serializers.BooleanField(required=False)


class EntryStatusSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    status = serializers.ChoiceField(choices=[s for s, _label in PluginCatalogStatus.CHOICES])
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    disable_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=200,
        help_text=_(
            "未启用原因，选填：管理员停用时填用户填写的原因；"
            "审核不通过时填固定文案「审核不通过」。不填时前端统一显示「该插件已被空间管理停用」"
        ),
    )
    replace_plugin_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["status"] == PluginCatalogStatus.ENABLE and "target_directory_id" not in self.initial_data:
            raise serializers.ValidationError("启用插件需要指定 target_directory_id（可为空表示未分类）")
        return attrs


class PluginDetailQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))


class ReferenceListQuerySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    scope = serializers.ChoiceField(choices=["all", "published", "draft"], required=False, default="all")
    keyword = serializers.CharField(required=False, allow_blank=True, default="")
    ordering = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=_(
            "排序：maintainer / -maintainer（按维护人）；`-` 前缀为降序。"
            "不传则按最近更新倒序。不支持的字段回落到默认顺序"
        ),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=10, min_value=1, max_value=200)


class ReasonSerializer(serializers.Serializer):
    """03 · 独立编辑「未启用配置」（未启用原因 + 建议替换插件），仅「未启用」态可改。"""

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=200,
        help_text=_("未启用原因，选填；不填时前端统一显示「该插件已被空间管理停用」"),
    )
    replace_plugin_id = serializers.IntegerField(required=False, allow_null=True)


class BatchCategorySerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class AiClassifySerializer(serializers.Serializer):
    """AI 分类建议的入参：单个或多个插件条目 id。

    - 单个：设计稿里「给某个插件单独设置目录」——传 1 个 id
    - 多个：新插件策略的批量场景——传一批 id 一次拿一批建议

    只返回建议、**不写库**，前端应用后再自行保存。
    """

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, help_text=_("插件条目 id 列表"))


class BatchStatusItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class BatchStatusSerializer(serializers.Serializer):
    space_id = serializers.IntegerField(help_text=_("空间ID"))
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    status = serializers.ChoiceField(choices=[s for s, _label in PluginCatalogStatus.CHOICES])
    target_directory_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    items = BatchStatusItemSerializer(many=True, required=False, default=list)
