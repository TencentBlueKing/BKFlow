import logging
from enum import Enum

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from bkflow.exceptions import SecondAuthError

logger = logging.getLogger("root")


def fill_plugin_info(remote_plugin):
    """
    将最新插件信息封装为本地蓝鲸插件
    """
    return BKPlugin(
        code=remote_plugin["plugin"]["code"],
        name=remote_plugin["plugin"]["name"],
        logo_url=remote_plugin["plugin"]["logo_url"],
        tag=remote_plugin["profile"]["tag"],
        created_time=remote_plugin["plugin"]["created"],
        updated_time=remote_plugin["plugin"]["updated"],
        introduction=remote_plugin["profile"]["introduction"],
        contact=remote_plugin["profile"]["contact"],
    )


def bulk_update_all_fields(model, object_list, batch_size=500):
    fields = [field.name for field in model._meta.fields if not field.primary_key and not field.auto_created]
    model.objects.bulk_update(object_list, fields, batch_size=batch_size)


class BKPluginManager(models.Manager):
    def bulk_update_bk_plugins(self, remote_plugins_dict):
        """
        批量更新插件信息
        """
        local_plugins = self.all()
        # 通过比较插件code，将最新插件分成新增、删除和待更新的code集合
        newest_codes = set(remote_plugins_dict.keys())
        local_code = set(plugin.code for plugin in local_plugins)
        new_codes = newest_codes - local_code
        deleted_codes = local_code - newest_codes
        existed_codes = newest_codes & local_code
        # 准备好批量创建的插件列表
        to_create_plugins = []
        for (code, plugin) in remote_plugins_dict.items():
            if code not in new_codes:
                continue
            to_create_plugins.append(fill_plugin_info(plugin))
        # 通过updated字段筛选出有变动的插件，准备好批量更新的插件列表
        to_update_plugins = []
        for plugin in local_plugins.filter(code__in=existed_codes):
            remote_plugin = remote_plugins_dict[plugin.code]
            if remote_plugin["plugin"]["updated"] != plugin.updated_time:
                to_update_plugins.append(fill_plugin_info(remote_plugin))
        # 开启事务进行批量操作
        with transaction.atomic():
            if to_create_plugins:
                # 每次同步检查一次权限记录，是否需要创建新记录
                BKPluginAuthentication.objects.create_by_codes(new_codes)
                local_plugins.bulk_create(to_create_plugins)
            if deleted_codes:
                local_plugins.filter(code__in=deleted_codes).delete()
            if to_update_plugins:
                bulk_update_all_fields(BKPlugin, to_update_plugins, batch_size=500)
            logger.info(f"蓝鲸插件同步完成，新增{len(new_codes)}个，删除{len(deleted_codes)}个，更新内容{len(to_update_plugins)}个")

    def get_plugin_by_manager(self, username):
        """
        根据用户管理员权限获取插件列表
        """
        # 仅获取该用户有管理员权限的蓝鲸插件
        return self.filter(contact__contains=username)


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
    contact = models.CharField(_("联系人，以逗号分隔"), max_length=255)
    extra_info = models.JSONField(_("额外信息"), default=dict)

    objects = BKPluginManager()

    class Meta:
        verbose_name = "蓝鲸插件"
        verbose_name_plural = "蓝鲸插件实时信息表"


class AuthorizeStatus(int, Enum):
    authorized = 1
    unauthorized = 0


def get_default_config():
    return {"white_list": ["*"]}


class BKPluginAuthenticationManager(models.Manager):
    def create_by_codes(self, new_codes):
        existing_codes = set(auth.code for auth in self.all())
        to_create_codes = set(new_codes) - existing_codes
        to_create_auth = []
        for code in to_create_codes:
            to_create_auth.append(BKPluginAuthentication(code=code))
        self.bulk_create(to_create_auth)

    def get_codes_by_space_id(self, space_id):
        """
        根据空间ID获取已被授权的插件code
        """
        queryset = self.filter(status=AuthorizeStatus.authorized)
        result_codes = []
        # JSON字段直接处理，减轻DB压力
        for auth in queryset:
            white_list = auth.config.get("white_list", [])
            if "*" in white_list or space_id in white_list:
                result_codes.append(auth.code)
        return result_codes

    # 批量检查插件授权状态
    @staticmethod
    def batch_check_authorization(activities):
        exist_code_list = [node["component"]["data"]["plugin_code"]["value"] for node in activities.values()]
        unauthorized_plugins = BKPluginAuthentication.objects.filter(
            code__in=exist_code_list, status=AuthorizeStatus.unauthorized
        ).values_list("code", flat=True)
        if unauthorized_plugins:
            logger.exception(f"流程中存在未授权插件：{unauthorized_plugins}")
            raise SecondAuthError(f"流程中存在未授权插件：{unauthorized_plugins}")


class BKPluginAuthentication(models.Model):
    """ "
    蓝鲸插件的授权记录
    """

    AuthStatus = (
        (AuthorizeStatus.authorized, _("已授权")),
        (AuthorizeStatus.unauthorized, _("未授权")),
    )

    code = models.CharField(_("插件code"), db_index=True, max_length=100)
    status = models.IntegerField(_("授权状态"), choices=AuthStatus, default=AuthorizeStatus.unauthorized)
    authorized_time = models.DateTimeField(_("授权时间"), null=True, blank=True)
    config = models.JSONField(_("授权配置，如使用范围等"), default=get_default_config)
    operator = models.CharField(_("授权人名称"), max_length=100, blank=True, default="")

    objects = BKPluginAuthenticationManager()

    class Meta:
        verbose_name = "蓝鲸插件授权记录"
        verbose_name_plural = "蓝鲸插件授权记录表"
