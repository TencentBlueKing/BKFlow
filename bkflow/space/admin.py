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

from django import forms
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from bkflow.exceptions import ValidationError as ConfigValidationError
from bkflow.space import models
from bkflow.space.configs import HarnessDeploymentConfig, SpaceConfigValueType


class SpaceConfigAdminForm(forms.ModelForm):
    """Select the active value field without changing the database storage contract."""

    class Meta:
        model = models.SpaceConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text_value"].required = False
        self.fields["text_value"].help_text = _("文本配置必填；JSON 配置无需填写占位文本。")
        self.fields["json_value"].help_text = _("Harness 可信部署绑定必须填写完整 JSON；保存不会自动开启任何开关。")

    def clean(self):
        values = super().clean()
        value_type = values.get("value_type")
        if value_type in (SpaceConfigValueType.TEXT.value, SpaceConfigValueType.REF.value) and not values.get(
            "text_value"
        ):
            self.add_error("text_value", _("文本配置必须填写配置值。"))
        if values.get("name") == HarnessDeploymentConfig.name:
            if value_type != SpaceConfigValueType.JSON.value:
                self.add_error("value_type", _("Harness 可信部署绑定必须使用 JSON 类型。"))
            elif "json_value" in values:
                try:
                    HarnessDeploymentConfig.validate(values["json_value"])
                except ConfigValidationError:
                    self.add_error("json_value", _("可信部署绑定不完整或格式错误，请核对接入文档中的必填字段。"))
        return values


@admin.register(models.Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "app_code", "platform_url", "create_type", "creator", "create_at")
    search_fields = ("name", "app_code", "platform_url")
    list_filter = ("name", "app_code", "create_type", "platform_url")
    ordering = ["-create_at"]


@admin.register(models.SpaceConfig)
class SpaceConfigAdmin(admin.ModelAdmin):
    form = SpaceConfigAdminForm
    list_display = ("id", "space_id", "name", "value_type", "text_value", "json_value")
    search_fields = ("space_id", "name", "value_type")
    list_filter = ("space_id", "name", "value_type")
    ordering = ["-space_id"]


@admin.register(models.Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "space_id", "name", "desc", "type", "content")
    search_fields = ("space_id", "name", "type")
    list_filter = ("space_id",)
    ordering = ["-id"]


@admin.register(models.CredentialScope)
class CredentialScopeAdmin(admin.ModelAdmin):
    list_display = ("id", "credential_id", "scope_type", "scope_value")
    search_fields = ("credential_id", "scope_type", "scope_value")
    list_filter = ("credential_id", "scope_type", "scope_value")
    ordering = ["-id"]
