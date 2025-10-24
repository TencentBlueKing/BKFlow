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
from enum import Enum

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

import env
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.exceptions import APIResponseError, ValidationError
from bkflow.space.configs import (
    BaseSpaceConfig,
    SpaceConfigHandler,
    SpaceConfigValueType,
    SuperusersConfig,
)
from bkflow.space.credential import CredentialDispatcher
from bkflow.space.exceptions import SpaceNotExists
from bkflow.utils.models import CommonModel, SecretSingleJsonField


class SpaceCreateType(Enum):
    # 通过API创建
    API = "API"
    # 通过页面创建
    WEB = "WEB"


class SpaceManager(models.Manager):
    MAX_SPACE_NUM_PER_APP = env.MAX_SPACE_NUM_PER_APP

    def is_app_code_reach_limit(self, app_code):
        return self.filter(app_code=app_code).count() > self.MAX_SPACE_NUM_PER_APP


class Space(CommonModel):
    CREATE_TYPE = (
        (SpaceCreateType.API.value, _("API")),
        (SpaceCreateType.WEB.value, _("WEB")),
    )

    id = models.AutoField(_("空间ID"), primary_key=True)
    # 空间名不允许重复
    name = models.CharField(_("空间名称"), max_length=32, null=False, blank=False, unique=True)
    app_code = models.CharField(_("应用ID"), max_length=32, null=False, blank=False)
    desc = models.CharField(_("空间描述"), max_length=128, null=True, blank=True)
    platform_url = models.CharField(_("平台提供服务的地址"), max_length=256, null=False, blank=False)
    create_type = models.CharField(_("空间创建的方式"), max_length=32, choices=CREATE_TYPE, default=SpaceCreateType.API.value)

    objects = SpaceManager()

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "platform_url": self.platform_url,
            "app_code": self.app_code,
            "create_type": self.create_type,
        }

    @classmethod
    def exists(cls, space_id):
        return cls.objects.filter(id=space_id, is_deleted=False).exists()

    class Meta:
        verbose_name = _("空间信息")
        verbose_name_plural = _("空间信息表")
        ordering = ["-id"]


class SpaceConfigManager(models.Manager):
    def get_space_ids_of_superuser(self, username):
        return self.filter(name=SuperusersConfig.name, json_value__contains=username).values_list("space_id", flat=True)

    def get_space_config_info(self, space_id: int, simplified: bool = True) -> list:
        """
        @summary: 获取space_id对应的空间相关配置信息
        @param space_id: 空间ID
        @param simplified: 是否简化返回结果
        @return: 所有空间相关配置信息
        非简化结果会返回所有过滤数据
        简化结果：[{"key": "name1", "value": "value1"}]
        """
        space_configs = self.filter(space_id=space_id).exclude(value_type=SpaceConfigValueType.REF.value)
        ref_config = self.filter(space_id=space_id, value_type=SpaceConfigValueType.REF.value)
        res = []
        if ref_config:
            client = TaskComponentClient(space_id=space_id)
            instance_ids = [config.id for config in ref_config]
            resp = client.get_engine_config(data={"interface_config_ids": instance_ids, "simplified": simplified})
            if not resp["result"]:
                raise APIResponseError(resp["message"])
            remote_data = resp["data"]
            for data in remote_data:
                data["id"] = data["interface_config_id"]
                # 要将 id 替换
            res += remote_data

        if simplified:
            res += [
                {
                    "key": config.name,
                    "value": (
                        config.json_value if config.value_type == SpaceConfigValueType.JSON.value else config.text_value
                    ),
                }
                for config in space_configs
            ]
        else:
            res += [config.to_json() for config in space_configs]
        return res

    def create_space_config(self, space_id: int, data: dict):
        value_type = SpaceConfigHandler.get_config(data["name"]).value_type

        # 两种情况处理 不是引用类型 直接创建
        if value_type != SpaceConfigValueType.REF.value:
            return self.create(**data)

        client = TaskComponentClient(space_id=space_id)
        with transaction.atomic():
            # 这里事务先执行本地 DB 创建 可以保证如果 api 调用失败能够回滚不产生脏数据
            instance = SpaceConfig.objects.create(space_id=space_id, name=data["name"], value_type=value_type)
            data["interface_config_id"] = instance.id
            resp = client.upsert_engine_config(data=data)
            if not resp["result"]:
                transaction.set_rollback(True)
                raise APIResponseError(resp["message"])

    def update_space_config(self, space_id: int, data: dict, instance):
        value_type = SpaceConfigHandler.get_config(data["name"]).value_type
        with transaction.atomic():
            # 这里事务先执行本地 DB 修改 可以保证如果 api 调用失败能够回滚不产生脏数据
            for attr, value in data.items():
                setattr(instance, attr, value)
            instance.save(update_fields=list(data.keys()))
            if value_type == SpaceConfigValueType.REF.value:
                client = TaskComponentClient(space_id=space_id)
                data["interface_config_id"] = instance.id
                resp = client.upsert_engine_config(data=data)
                if not resp["result"]:
                    transaction.set_rollback(True)
                    raise APIResponseError(resp["message"])

    def delete_space_config(self, pk: int):
        instance = self.get(id=pk)
        space_id = instance.space_id
        value_type = SpaceConfigHandler.get_config(instance.name).value_type

        with transaction.atomic():
            instance.delete()
            if value_type == SpaceConfigValueType.REF.value:
                client = TaskComponentClient(space_id=space_id)
                resp = client.delete_engine_config(data={"interface_config_ids": [pk]})
                if not resp["result"]:
                    transaction.set_rollback(True)
                    raise APIResponseError(resp["message"])

    def batch_update(self, space_id: int, configs: dict):
        existing_space_configs = list(self.filter(space_id=space_id, name__in=list(configs.keys())))
        existing_space_config_keys = [space_config.name for space_config in existing_space_configs]
        for existing_space_config in existing_space_configs:
            if existing_space_config.name not in configs:
                continue
            if SpaceConfigHandler.get_config(existing_space_config.name).value_type == SpaceConfigValueType.JSON.value:
                existing_space_config.json_value = configs[existing_space_config.name]
            else:
                existing_space_config.text_value = configs[existing_space_config.name]

        create_space_configs = []
        valid_keys = list(SpaceConfigHandler.get_all_configs().keys())
        for k, v in configs.items():
            if k in existing_space_config_keys or k not in valid_keys:
                continue
            data = {"space_id": space_id, "name": k, "value_type": SpaceConfigHandler.get_config(k).value_type}
            if data["value_type"] == SpaceConfigValueType.JSON.value:
                data["json_value"] = v
            else:
                data["text_value"] = v
            create_space_configs.append(SpaceConfig(**data))

        SpaceConfig.objects.bulk_update(existing_space_configs, ["text_value", "json_value"])
        SpaceConfig.objects.bulk_create(create_space_configs)


class SpaceConfig(models.Model):
    CONFIG_CHOICES = [(name, config.desc) for name, config in SpaceConfigHandler.get_all_configs().items()]
    CONFIG_VALUE_TYPE_CHOICES = [
        (SpaceConfigValueType.JSON.value, "JSON"),
        (SpaceConfigValueType.TEXT.value, _("文本")),
        (SpaceConfigValueType.REF.value, _("引用")),
    ]

    space_id = models.IntegerField(_("空间ID"))
    value_type = models.CharField(
        _("配置类型"), choices=CONFIG_VALUE_TYPE_CHOICES, default=SpaceConfigValueType.TEXT.value, max_length=32
    )
    name = models.CharField(_("配置项"), choices=CONFIG_CHOICES, max_length=32)
    text_value = models.CharField(_("配置值"), max_length=128, default="")
    json_value = models.JSONField(_("配置值(JSON)"), default=dict, blank=True)

    objects = SpaceConfigManager()

    class Meta:
        verbose_name = _("空间配置")
        verbose_name_plural = _("空间配置表")
        unique_together = ("space_id", "name")

    def to_json(self):
        return {
            "id": self.id,
            "space_id": self.space_id,
            "name": self.name,
            "value_type": self.value_type,
            "value": self.text_value,
            "json_value": self.json_value,
        }

    @classmethod
    def exists(cls, space_id, config_name):
        return cls.objects.filter(space_id=space_id, name=config_name).exists()

    @classmethod
    def get_config(cls, space_id, config_name, *args, **kwargs):
        try:
            config: SpaceConfig = cls.objects.get(space_id=space_id, name=config_name)
            return SpaceConfigHandler.get_config(config_name).get_value(config, *args, **kwargs)
        except cls.DoesNotExist:
            config: BaseSpaceConfig = SpaceConfigHandler.get_config(config_name)
            if not config:
                raise ValidationError(_("不存在该配置项"))
            return config.default_value


class CredentialType(Enum):
    # 蓝鲸应用凭证
    BK_APP = "BK_APP"
    # 蓝鲸登录态凭证
    BK_ACCESS_TOKEN = "BK_ACCESS_TOKEN"
    # 用户名+密码
    BASIC_AUTH = "BASIC_AUTH"
    # 自定义凭证
    CUSTOM = "CUSTOM"


class Credential(CommonModel):
    CREDENTIAL_CHOICES = [
        (CredentialType.BK_APP.value, _("蓝鲸应用凭证")),
        (CredentialType.BK_ACCESS_TOKEN.value, _("蓝鲸登录态凭证")),
        (CredentialType.BASIC_AUTH.value, _("用户名+密码")),
        (CredentialType.CUSTOM.value, _("自定义")),
    ]

    space_id = models.IntegerField(_("空间ID"))
    name = models.CharField(_("凭证名"), max_length=32)
    desc = models.CharField(_("凭证描述"), max_length=128, null=True, blank=True)
    type = models.CharField(_("凭证类型"), max_length=32, choices=CREDENTIAL_CHOICES)
    content = SecretSingleJsonField(_("凭证内容"), null=True, blank=True, default=dict)

    def display_json(self):
        credential = CredentialDispatcher(self.type, data=self.content)
        display_value = credential.display_value()
        return {
            "id": self.id,
            "space_id": self.space_id,
            "desc": self.desc,
            "type": self.type,
            "content": display_value,
        }

    @property
    def value(self):
        credential = CredentialDispatcher(self.type, data=self.content)
        return credential.value()

    @classmethod
    def create_credential(cls, space_id, name, type, content, creator, desc=None):
        """
        创建一个凭证

        :param space_id: 空间ID
        :param name: 凭证名称
        :param type: 凭证类型
        :param content: 凭证内容
        :param creator: 创建者
        :param desc: 凭证描述（可选）

        :return: 创建的凭证实例
        """
        if not Space.exists(space_id):
            raise SpaceNotExists("space_id: {}".format(space_id))
        credential = CredentialDispatcher(type, data=content)
        validate_data = credential.validate_data()
        credential = cls(
            space_id=space_id,
            name=name,
            desc=desc,
            type=type,
            content=validate_data,
            creator=creator,
            updated_by=creator,
        )
        credential.save()
        return credential

    def update_credential(self, content):
        """
        更新凭证内容

        :param content: 新的凭证内容
        """
        credential = CredentialDispatcher(self.type, data=content)
        validate_data = credential.validate_data()
        self.content = validate_data
        self.save()

    def get_scopes(self):
        """
        获取凭证的作用域列表

        :return: 凭证作用域查询集
        """
        return CredentialScope.objects.filter(credential_id=self.id)

    def has_scope(self):
        """
        检查凭证是否设置了作用域

        :return: 如果设置了作用域返回 True，否则返回 False
        """
        return self.get_scopes().exists()

    def can_use_in_scope(self, template_scope_type, template_scope_value):
        """
        检查凭证是否可以在指定作用域中使用
        如果凭证没有设置作用域，则可以在任何作用域使用
        如果模板没有作用域（scope_type和scope_value都为空），则可以使用任何凭证
        否则，凭证的作用域必须匹配模板的作用域

        :param self: 凭证实例
        :param template_scope_type: 作用域类型
        :param template_scope_value: 作用域值
        :return: 如果可以使用返回 True，否则返回 False
        """
        if not self.has_scope():
            # 凭证没有设置作用域，不允许被使用
            return False

        if not template_scope_type and not template_scope_value:
            # 模板没有作用域，可以使用任何凭证
            return True

        # 检查是否有匹配的作用域
        return (
            self.get_scopes()
            .filter(
                scope_type=template_scope_type,
                scope_value=template_scope_value,
            )
            .exists()
        )

    class Meta:
        verbose_name = _("空间凭证")
        verbose_name_plural = _("空间凭证表")
        unique_together = ("space_id", "name")


class CredentialScope(models.Model):
    """
    凭证作用域
    用于控制凭证的使用范围
    未关联任何作用域的凭证不受作用域限制，可以在任何地方使用
    """

    id = models.AutoField(primary_key=True)
    credential_id = models.IntegerField(_("凭证ID"), db_index=True)
    scope_type = models.CharField(_("作用域类型"), max_length=128, null=True, blank=True)
    scope_value = models.CharField(_("作用域值"), max_length=128, null=True, blank=True)

    class Meta:
        verbose_name = _("凭证作用域")
        verbose_name_plural = _("凭证作用域表")
        indexes = [
            models.Index(fields=["credential_id", "scope_type", "scope_value"]),
        ]
