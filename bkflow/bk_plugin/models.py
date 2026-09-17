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

from django.conf import settings
from django.db import models, transaction
from django.utils.timezone import localtime
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError

import env
from bkflow.constants import ALL_SPACE, WHITE_LIST
from bkflow.exceptions import PluginUnAuthorization

logger = logging.getLogger("root")


class BKPluginManager(models.Manager):
    def for_space(self, space_id):
        """统一目录和详情入口的租户范围，system 插件可共享。"""
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return self.all()
        from bkflow.bk_plugin.tenant import get_plugin_tenant_id

        return self.filter(tenant_id__in=[get_plugin_tenant_id(space_id), "system"])

    def fill_plugin_info(self, remote_plugin):
        """
        将最新插件信息封装为本地蓝鲸插件
        """
        managers = (
            remote_plugin["profile"]["contact"].replace(";", ",").split(",")
            if remote_plugin["profile"]["contact"]
            else [remote_plugin["plugin"]["creator"]]
        )

        return BKPlugin(
            code=remote_plugin["plugin"]["code"],
            name=remote_plugin["plugin"]["name"],
            logo_url=remote_plugin["plugin"]["logo_url"],
            tag=remote_plugin["profile"]["tag"] or 0,
            created_time=remote_plugin["plugin"]["created"],
            updated_time=remote_plugin["plugin"]["updated"],
            introduction=remote_plugin["profile"]["introduction"],
            managers=managers,
        )

    def is_same_plugin(self, plugin_a, plugin_b, fields_to_compare):
        for field in fields_to_compare:
            if getattr(plugin_a, field) != getattr(plugin_b, field):
                return False
        return True

    def sync_bk_plugins(self, remote_plugins_dict, tenant_id=None):
        """
        批量更新插件信息
        """
        if settings.ENABLE_MULTI_TENANT_MODE:
            return self._sync_tenant_plugins(remote_plugins_dict, tenant_id)
        if not remote_plugins_dict:
            return
        # 比较插件code和更新时间
        local_plugins = {plugin.code: plugin for plugin in self.all()}
        local_plugin_codes = set(local_plugins.keys())
        remote_plugin_codes = set(remote_plugins_dict.keys())
        codes_to_add = set(remote_plugin_codes - local_plugin_codes)
        codes_to_delete = set(local_plugin_codes - remote_plugin_codes)
        codes_to_compare = set(local_plugin_codes & remote_plugin_codes)
        plugins_to_update = set()
        # 单租户同步不改变已记录的租户归属，也不依赖远端新字段。
        fields_to_compare = [f.name for f in BKPlugin._meta.fields if not f.primary_key and f.name != "tenant_id"]
        for code in codes_to_compare:
            remote_plugin = self.fill_plugin_info(remote_plugins_dict[code])
            local_plugin = local_plugins[code]
            if not self.is_same_plugin(remote_plugin, local_plugin, fields_to_compare):
                plugins_to_update.add(remote_plugin)
                continue
        plugins_to_add = [self.fill_plugin_info(remote_plugins_dict[code]) for code in codes_to_add]
        # 开启事务进行批量操作
        with transaction.atomic():
            if codes_to_delete:
                self.filter(code__in=codes_to_delete).delete()
            if codes_to_add:
                self.bulk_create(plugins_to_add)
            if plugins_to_update:
                self.bulk_update(plugins_to_update, fields=fields_to_compare)
        logger.info("本次蓝鲸插件同步，删除{}个".format(len(codes_to_delete)))
        logger.info("本次蓝鲸插件同步，新增{}个".format(len(codes_to_add)))
        logger.info("本次蓝鲸插件同步，更新{}个".format(len(plugins_to_update)))

    @transaction.atomic
    def _sync_tenant_plugins(self, remote_plugins_dict, tenant_id):
        """完整拉取成功后更新一个租户；空结果也只清理该租户，未知归属留待重同步。"""
        if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 64:
            raise ValidationError("插件同步缺少有效租户")
        remote_plugins = {}
        for info in remote_plugins_dict.values():
            # 当前 PaaS 目录 API 按 Application.tenant_id 精确过滤，返回体不含租户字段。
            declared_tenant = info["plugin"].get("tenant_id")
            if declared_tenant is not None and declared_tenant != tenant_id:
                raise ValidationError("插件目录返回的租户与同步范围不一致")
            plugin = self.fill_plugin_info(info)
            plugin.tenant_id = tenant_id
            remote_plugins[plugin.code] = plugin
        local_plugins = {
            plugin.code: plugin
            for plugin in self.select_for_update().filter(
                models.Q(tenant_id=tenant_id) | models.Q(code__in=remote_plugins)
            )
        }
        for code in remote_plugins:
            if code in local_plugins and local_plugins[code].tenant_id not in ("", tenant_id):
                raise ValidationError("同一插件 code 出现在不同租户，拒绝覆盖已有归属")
        to_delete = set(local_plugins) - set(remote_plugins)
        if to_delete:
            self.filter(tenant_id=tenant_id, code__in=to_delete).delete()
        to_create = [plugin for code, plugin in remote_plugins.items() if code not in local_plugins]
        to_update = [plugin for code, plugin in remote_plugins.items() if code in local_plugins]
        if to_create:
            self.bulk_create(to_create)
        if to_update:
            self.bulk_update(to_update, fields=[f.name for f in BKPlugin._meta.fields if not f.primary_key])
        logger.info("租户插件同步完成 tenant_id=%s count=%s", tenant_id, len(remote_plugins))


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
    tenant_id = models.CharField(_("插件所属租户"), max_length=64, default="", blank=True, db_index=True)

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
    return {WHITE_LIST: [{"id": ALL_SPACE, "name": ALL_SPACE}]}


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
            "status_update_time": (
                localtime(self.status_update_time).strftime("%Y-%m-%d %H:%M:%S") if self.status_update_time else ""
            ),
            "config": self.config,
            "status_updator": self.status_updator,
        }
