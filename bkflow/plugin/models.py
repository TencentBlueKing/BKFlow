# -*- coding: utf-8 -*-
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

from django.db import models


class SpacePluginConfigManager(models.Manager):
    def get_space_allow_list(self, space_id):
        qs = self.filter(space_id=space_id)
        if not qs.exists():
            return []
        return qs.first().allow_list


class SpacePluginConfig(models.Model):
    """
    插件空间配置, 系统级配置，用于限制内置插件的空间使用范围
    config格式如: {"allow_list": ["plugin_code1", "plugin_code2"]}
    """

    ALLOW_LIST = "allow_list"

    space_id = models.IntegerField(verbose_name="空间ID", db_index=True)
    config = models.JSONField(verbose_name="插件配置")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    objects = SpacePluginConfigManager()

    class Meta:
        verbose_name = "空间插件配置"
        verbose_name_plural = "空间插件配置"
        app_label = "plugin"

    def __str__(self):
        return f"{self.space_id}: {self.config}"

    @property
    def allow_list(self):
        return self.config.get(self.ALLOW_LIST, [])


class OpenPluginCatalogIndex(models.Model):
    class Status:
        AVAILABLE = "available"
        UNAVAILABLE = "unavailable"

        CHOICES = (
            (AVAILABLE, "available"),
            (UNAVAILABLE, "unavailable"),
        )

    space_id = models.IntegerField(verbose_name="空间ID", db_index=True)
    source_key = models.CharField(verbose_name="开放插件来源", max_length=64)
    plugin_id = models.CharField(verbose_name="开放插件ID", max_length=128)
    plugin_code = models.CharField(verbose_name="插件编码", max_length=128)
    plugin_name = models.CharField(verbose_name="插件名称", max_length=255)
    plugin_source = models.CharField(verbose_name="插件来源类型", max_length=64)
    group_name = models.CharField(verbose_name="插件分组", max_length=128, blank=True, default="")
    wrapper_version = models.CharField(verbose_name="包装器版本", max_length=32, blank=True, default="")
    default_version = models.CharField(verbose_name="默认业务版本", max_length=64, blank=True, default="")
    latest_version = models.CharField(verbose_name="最新业务版本", max_length=64, blank=True, default="")
    versions = models.JSONField(verbose_name="可用业务版本列表", default=list, blank=True)
    meta_url_template = models.CharField(verbose_name="插件详情模板URL", max_length=1024, blank=True, default="")
    description = models.TextField(verbose_name="插件描述", blank=True, default="")
    status = models.CharField(
        verbose_name="插件状态",
        max_length=32,
        choices=Status.CHOICES,
        default=Status.AVAILABLE,
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "开放插件目录索引"
        verbose_name_plural = "开放插件目录索引"
        app_label = "plugin"
        unique_together = ("space_id", "source_key", "plugin_id")
        indexes = [
            models.Index(fields=["space_id", "source_key"]),
            models.Index(fields=["space_id", "status"]),
        ]

    def __str__(self):
        return f"{self.space_id}:{self.source_key}:{self.plugin_id}"


class SpaceOpenPluginAvailability(models.Model):
    space_id = models.IntegerField(verbose_name="空间ID", db_index=True)
    source_key = models.CharField(verbose_name="开放插件来源", max_length=64)
    plugin_id = models.CharField(verbose_name="开放插件ID", max_length=128)
    enabled = models.BooleanField(verbose_name="是否已开启", default=False)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "空间开放插件可用性"
        verbose_name_plural = "空间开放插件可用性"
        app_label = "plugin"
        unique_together = ("space_id", "source_key", "plugin_id")
        indexes = [models.Index(fields=["space_id", "source_key", "enabled"])]

    def __str__(self):
        return f"{self.space_id}:{self.source_key}:{self.plugin_id}:{self.enabled}"


class OpenPluginRunCallbackRef(models.Model):
    task_id = models.BigIntegerField(verbose_name="任务ID", db_index=True)
    node_id = models.CharField(verbose_name="节点ID", max_length=64, db_index=True)
    node_version = models.CharField(verbose_name="节点版本", max_length=32, blank=True, default="")
    client_request_id = models.CharField(verbose_name="客户端请求ID", max_length=128, unique=True)
    open_plugin_run_id = models.CharField(verbose_name="开放插件运行ID", max_length=64, unique=True, db_index=True)
    callback_token_digest = models.CharField(verbose_name="回调令牌摘要", max_length=128)
    callback_expire_at = models.DateTimeField(verbose_name="回调令牌过期时间")
    plugin_source = models.CharField(verbose_name="插件来源类型", max_length=64, blank=True, default="")
    source_key = models.CharField(verbose_name="开放插件来源", max_length=64, blank=True, default="")
    plugin_id = models.CharField(verbose_name="开放插件ID", max_length=128)
    plugin_version = models.CharField(verbose_name="开放插件版本", max_length=64, blank=True, default="")
    cancel_url = models.CharField(verbose_name="开放插件取消URL", max_length=1024, blank=True, default="")
    credential_key = models.CharField(verbose_name="取消调用使用的凭证key", max_length=128, blank=True, default="")
    consumed_at = models.DateTimeField(verbose_name="回调消费时间", null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "开放插件回调映射"
        verbose_name_plural = "开放插件回调映射"
        app_label = "plugin"
        indexes = [
            models.Index(fields=["task_id", "node_id"]),
            models.Index(fields=["callback_expire_at"]),
        ]

    def __str__(self):
        return f"{self.task_id}:{self.node_id}:{self.open_plugin_run_id}"
