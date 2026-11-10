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

from bkflow.plugin_catalog.models import PluginType
from bkflow.plugin_catalog.services.picker_service import PluginPickerService


class PluginPickerQuerySerializer(serializers.Serializer):
    """
    画布统一选择列表入参。
    """

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    directory_id = serializers.CharField(
        help_text=_("all/recommend/uncategorized/具体目录id（含子级）"), required=False, default="all"
    )
    plugin_type = serializers.ChoiceField(
        choices=["all", PluginType.BUILTIN, PluginType.BK_PLUGIN, PluginType.API],
        required=False,
        default="all",
        help_text=_("插件类型筛选，与管理侧三类型枚举一致"),
    )
    keyword = serializers.CharField(help_text=_("模糊匹配插件名称/描述"), required=False, allow_blank=True, default="")
    ordering = serializers.ChoiceField(
        choices=list(PluginPickerService.ORDERING_CHOICES),
        required=False,
        default="recommend",
        help_text=_("recommend(默认，推荐优先)/-publish_time/publish_time/name/-usage_count/usage_count"),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)
