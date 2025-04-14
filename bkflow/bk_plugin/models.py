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
import logging
from enum import Enum

from django.db import models, transaction
from django.utils.timezone import localtime
from django.utils.translation import ugettext_lazy as _

import env
from bkflow.constants import ALL_SPACE, WHITE_LIST
from bkflow.exceptions import PluginUnAuthorization

logger = logging.getLogger("root")


class BKPluginManager(models.Manager):
    def fill_plugin_info(self, remote_plugin):
        """
        将最新插件信息封装为本地蓝鲸插件
        """
        managers = set()
        if remote_plugin["profile"]["contact"]:
            managers.update(remote_plugin["profile"]["contact"].split(","))
        if remote_plugin["plugin"]["creator"]:
            managers.add(remote_plugin["plugin"]["creator"])
        return BKPlugin(
            code=remote_plugin["plugin"]["code"],
            name=remote_plugin["plugin"]["name"],
            logo_url=remote_plugin["plugin"]["logo_url"],
            tag=remote_plugin["profile"]["tag"],
            created_time=remote_plugin["plugin"]["created"],
            updated_time=remote_plugin["plugin"]["updated"],
            introduction=remote_plugin["profile"]["introduction"],
            managers=list(managers),
        )

    def is_same_plugin(self, plugin_a, plugin_b, fields_to_compare):
        for field in fields_to_compare:
            if getattr(plugin_a, field) != getattr(plugin_b, field):
                return False
            return True

    def sync_bk_plugins(self, remote_plugins_dict):
        """
        批量更新插件信息
        """
        if not remote_plugins_dict:
            return
        # 比较插件code和更新时间
        local_plugins = {plugin.code: plugin for plugin in self.all()}
        local_plugin_codes = set(local_plugins.keys())
        remote_plugin_codes = set(remote_plugins_dict.keys())
        codes_to_add = set(remote_plugin_codes - local_plugin_codes)
        codes_to_delete = set(local_plugin_codes - remote_plugin_codes)
        codes_to_compare = set(local_plugin_codes & remote_plugin_codes)
        fields_to_compare = [f.name for f in BKPlugin._meta.fields if not f.primary_key]
        for code in codes_to_compare:
            remote_plugin = self.fill_plugin_info(remote_plugins_dict[code])
            local_plugin = local_plugins[code]
            if not self.is_same_plugin(remote_plugin, local_plugin, fields_to_compare):
                codes_to_delete.update(code)
                codes_to_add.update(code)
                continue
        plugins_to_add = [self.fill_plugin_info(remote_plugins_dict[code]) for code in codes_to_add]
        # 开启事务进行批量操作
        with transaction.atomic():
            if codes_to_delete:
                self.filter(code__in=codes_to_delete).delete()
                logger.info("本次蓝鲸插件同步，删除{}个".format(len(codes_to_delete)))
            if codes_to_add:
                self.bulk_create(plugins_to_add)
                logger.info("本次蓝鲸插件同步，新增{}个".format(len(codes_to_add)))


class BKPlugin(models.Model):
    """
    蓝鲸插件数据
    """

    code = models.CharField(_("插件code"), primary_key=True, max_length=100)
    name = models.CharField(_("插件名称"), max_length=255)
    tag = models.IntegerField(_("插件隶属分类"), db_index=True, null=False)
    logo_url = models.CharField(_("插件图片url"), max_length=255)
    created_time = models.CharField(_("插件创建时间"), null=True, blank=True, max_length=255)
    updated_time = models.CharField(_("插件更新时间"), null=True, blank=True, max_length=255)
    introduction = models.CharField(_("插件简介"), max_length=255)
    managers = models.JSONField(_("插件管理员列表"), default=list)
    extra_info = models.JSONField(_("额外信息"), default=dict)

    objects = BKPluginManager()

    class Meta:
        verbose_name = "蓝鲸插件"
        verbose_name_plural = "蓝鲸插件"


class AuthStatus(int, Enum):
    authorized = 1
    unauthorized = 0


def get_default_config():
    return {WHITE_LIST: [ALL_SPACE]}


def get_default_list_config():
    return {WHITE_LIST: [{"id": ALL_SPACE, "name": "all_space"}]}


class BKPluginAuthorizationManager(models.Manager):
    def get_codes_by_space_id(self, space_id: str):
        """
        根据空间ID获取已被授权的插件code
        """
        authorized_dict = self.filter(status=AuthStatus.authorized)
        result_codes = []
        for obj in authorized_dict:
            white_list = obj.white_list
            if ALL_SPACE in white_list or space_id in white_list:
                result_codes.append(obj.code)
        return result_codes

    # 批量检查插件授权状态
    def batch_check_authorization(self, exist_code_list, space_id: str):
        if not env.ENABLE_BK_PLUGIN_AUTHORIZATION:
            return
        authorized_codes = set(self.filter(code__in=exist_code_list).values_list("code", flat=True)) & set(
            self.get_codes_by_space_id(space_id)
        )

        unauthorized_plugins = list(set(exist_code_list) - authorized_codes)
        if unauthorized_plugins:
            logger.exception(f"流程中存在未授权插件：{unauthorized_plugins}")
            raise PluginUnAuthorization(f"流程中存在未授权插件：{unauthorized_plugins}")


class BKPluginAuthorization(models.Model):
    """ "
    蓝鲸插件的授权记录
    """

    AUTH_STATUS_CHOICES = (
        (AuthStatus.authorized, _("已授权")),
        (AuthStatus.unauthorized, _("未授权")),
    )

    code = models.CharField(_("插件code"), db_index=True, max_length=100)
    status = models.IntegerField(_("授权状态"), choices=AUTH_STATUS_CHOICES, default=AuthStatus.unauthorized.value)
    status_update_time = models.DateTimeField(_("最近一次授权操作时间"), null=True, blank=True)
    config = models.JSONField(_("授权配置，如使用范围等"), default=get_default_config)
    status_updator = models.CharField(_("最近一次授权操作的人员名称"), max_length=100, blank=True, default="")

    objects = BKPluginAuthorizationManager()

    class Meta:
        verbose_name = "蓝鲸插件授权记录"
        verbose_name_plural = "蓝鲸插件授权记录"

    @property
    def white_list(self):
        return self.config[WHITE_LIST]

    def to_json(self):
        return {
            "code": self.code,
            "status": self.status,
            "status_update_time": localtime(self.status_update_time).strftime("%Y-%m-%d %H:%M:%S")
            if self.status_update_time
            else "",
            "config": self.config,
            "status_updator": self.status_updator,
        }
