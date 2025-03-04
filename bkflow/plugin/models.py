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

    def __str__(self):
        return f"{self.space_id}: {self.config}"

    @property
    def allow_list(self):
        return self.config.get(self.ALLOW_LIST, [])
