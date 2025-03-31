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
from django.utils.translation import ugettext_lazy as _

import env
from bkflow.constants import ALL_SPACE, WHITE_LIST
from bkflow.exceptions import UnAuthorization

logger = logging.getLogger("root")


class BKPluginManager(models.Manager):
    def fill_plugin_info(self, remote_plugin):
        """
        将最新插件信息封装为本地蓝鲸插件
        """
        manager = set(remote_plugin["profile"]["contact"].split(","))
        if remote_plugin["plugin"]["creator"]:
            manager.add(remote_plugin["plugin"]["creator"])
        return BKPlugin(
            code=remote_plugin["plugin"]["code"],
            name=remote_plugin["plugin"]["name"],
            logo_url=remote_plugin["plugin"]["logo_url"],
            tag=remote_plugin["profile"]["tag"],
            created_time=remote_plugin["plugin"]["created"],
            updated_time=remote_plugin["plugin"]["updated"],
            introduction=remote_plugin["profile"]["introduction"],
            manager=list(manager),
        )

    def sync_bk_plugins(self, remote_plugins_dict):
        """
        批量更新插件信息
        """
        local_plugins = self.all()
        # 比较插件code和更新时间
        remote_pairs = set((code, plugin["plugin"]["updated"]) for (code, plugin) in remote_plugins_dict.items())
        local_pairs = set((plugin.code, plugin.updated_time) for plugin in local_plugins)
        to_create_pairs = remote_pairs - local_pairs
        logger.info(f"蓝鲸插件同步过程新增插件{len(to_create_pairs)}个")
        # 准备好批量创建的插件列表
        to_create_plugins = [self.fill_plugin_info(remote_plugins_dict[pair[0]]) for pair in set(to_create_pairs)]
        to_delete_codes = [pair[0] for pair in set(local_pairs - remote_pairs)]
        logger.info(f"蓝鲸插件同步过程删除插件{len(to_delete_codes)}")
        # 开启事务进行批量操作
        with transaction.atomic():
            if to_delete_codes:
                local_plugins.filter(code__in=to_delete_codes).delete()
            if to_create_plugins:
                # 每次同步检查一次权限记录，是否需要创建新记录
                local_plugins.bulk_create(to_create_plugins)
            logger.info("蓝鲸插件同步完成")

    def get_plugin_by_manager(self, username):
        """
        根据用户管理员权限获取插件列表
        """
        # 仅获取该用户有管理员权限的蓝鲸插件
        return self.filter(manager__contains=username)


class BKPlugin(models.Model):
    """
    蓝鲸插件数据
    """

    code = models.CharField(_("插件code"), primary_key=True, max_length=100)
    name = models.CharField(_("插件名称"), max_length=255)
    tag = models.IntegerField(_("插件隶属分类"), db_index=True, null=False)
    logo_url = models.CharField(_("插件图片url"), max_length=255)
    created_time = models.DateTimeField(_("创建时间"), null=True, blank=True)
    updated_time = models.DateTimeField(_("更新时间"), null=True, blank=True)
    introduction = models.CharField(_("插件简介"), max_length=255)
    manager = models.JSONField(_("插件管理员列表"), default=list)
    extra_info = models.JSONField(_("额外信息"), default=dict)

    objects = BKPluginManager()

    class Meta:
        verbose_name = "蓝鲸插件"
        verbose_name_plural = "蓝鲸插件"


class AuthStatus(int, Enum):
    authorized = 1
    unauthorized = 0


def get_default_config():
    return {WHITE_LIST: ALL_SPACE}


class BKPluginAuthorizationManager(models.Manager):
    def get_codes_by_space_id(self, space_id):
        """
        根据空间ID获取已被授权的插件code
        """
        authorized_dict = self.filter(status=AuthStatus.authorized).values("code", "config")
        result_codes = []
        for obj in authorized_dict:
            white_list = obj.get("config").get(WHITE_LIST)
            if ALL_SPACE in white_list or space_id in white_list:
                result_codes.append(obj.get("code"))
        return result_codes

    # 批量检查插件授权状态
    @staticmethod
    def batch_check_authorization(exist_code_list):
        if not env.USE_BK_PLUGIN_AUTHORIZATION:
            return []
        authorized_codes = set(
            BKPluginAuthorization.objects.filter(code__in=exist_code_list, status=AuthStatus.authorized).values_list(
                "code", flat=True
            )
        )
        unauthorized_plugins = list(set(exist_code_list) - authorized_codes)
        if unauthorized_plugins:
            logger.exception(f"流程中存在未授权插件：{unauthorized_plugins}")
            raise UnAuthorization(f"流程中存在未授权插件：{unauthorized_plugins}")


class BKPluginAuthorization(models.Model):
    """ "
    蓝鲸插件的授权记录
    """

    AUTH_STATUS_CHOICES = (
        (AuthStatus.authorized, _("已授权")),
        (AuthStatus.unauthorized, _("未授权")),
    )

    code = models.CharField(_("插件code"), db_index=True, max_length=100)
    status = models.IntegerField(_("授权状态"), choices=AUTH_STATUS_CHOICES, default=AuthStatus.unauthorized)
    authorized_time = models.DateTimeField(_("授权时间"), null=True, blank=True)
    config = models.JSONField(_("授权配置，如使用范围等"), default=get_default_config())
    operator = models.CharField(_("授权人名称"), max_length=100, blank=True, default="")

    objects = BKPluginAuthorizationManager()

    class Meta:
        verbose_name = "蓝鲸插件授权记录"
        verbose_name_plural = "蓝鲸插件授权记录"

    def to_json(self):
        return {
            "code": self.code,
            "status": self.status,
            "authorized_time": self.authorized_time.strftime("%Y-%m-%d %H:%M:%S") if self.authorized_time else "",
            "config": self.config,
            "operator": self.operator,
        }
