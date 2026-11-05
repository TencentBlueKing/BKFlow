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


class PluginIdentitySerializer(serializers.Serializer):
    plugin_type = serializers.ChoiceField(choices=[p for p, _label in PluginType.CHOICES])
    source_key = serializers.CharField(required=False, allow_blank=True, default="")
    plugin_code = serializers.CharField()
    plugin_version = serializers.CharField(required=False, allow_blank=True, default="")


class PluginStatusesSerializer(serializers.Serializer):
    """批量查询插件当前状态：节点配置面板打开时一次性查出画布内所有节点的插件状态。"""

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    items = PluginIdentitySerializer(many=True, help_text=_("画布内节点引用的插件身份列表"))


class PluginVersionsQuerySerializer(serializers.Serializer):
    """13 · 插件可选版本列表。

    文档里的路径形式是 `plugins/<plugin_type>/<source_key>/<plugin_code>/versions/`，
    但 builtin/bk_plugin 的 source_key 恒为空串，无法放进 URL 路径段，
    因此改为 query 参数形式（与其余接口的 space_id 口径一致）。
    """

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    plugin_type = serializers.ChoiceField(choices=[p for p, _label in PluginType.CHOICES])
    source_key = serializers.CharField(required=False, allow_blank=True, default="")
    plugin_code = serializers.CharField()


class VersionDiffSerializer(serializers.Serializer):
    """13 · 版本切换/换插件的参数差异计算，也供 12 场景③（换插件时入参重新映射）复用。"""

    space_id = serializers.IntegerField(help_text=_("空间ID"))
    from_plugin = PluginIdentitySerializer()
    to_plugin = PluginIdentitySerializer()
    current_inputs = serializers.DictField(required=False, default=dict)
