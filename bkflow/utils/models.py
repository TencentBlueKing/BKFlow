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
import hashlib
import json

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from pipeline.models import CompressJSONField, SnapshotManager

from bkflow.utils.crypt import BaseCrypt
from bkflow.utils.md5 import compute_pipeline_md5


class CommonModel(models.Model):
    """基础字段"""

    creator = models.CharField(_("创建人"), max_length=32, null=True, blank=True)
    create_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    update_at = models.DateTimeField(_("更新时间"), auto_now=True)
    updated_by = models.CharField(_("修改人"), max_length=32, null=True, blank=True)
    is_deleted = models.BooleanField(_("是否软删除"), default=False, db_index=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.save()

    def hard_delete(self):
        super().delete()


class CommonSnapshotManager(SnapshotManager):
    def get_or_create_snapshot(self, data):
        h = hashlib.md5()
        h.update(json.dumps(data).encode("utf-8"))
        try:
            snapshot = self.get(md5sum=h.hexdigest())
        except self.model.DoesNotExist:
            snapshot = self.create(md5sum=h.hexdigest(), data=data)
        return snapshot


class CommonSnapshot(models.Model):
    """
    默认模板快照
    """

    id = models.BigAutoField(_("快照ID"), primary_key=True)
    md5sum = models.CharField(_("快照字符串的md5sum"), max_length=32, db_index=True)
    create_time = models.DateTimeField(_("创建时间"), auto_now_add=True)
    data = CompressJSONField(null=True, blank=True, help_text=_("存储的数据"))

    class Meta:
        abstract = True

    def __unicode__(self):
        return str(self.md5sum)

    def has_change(self, data):
        """
        检测 data 的 md5 是否和当前存储的不一致
        @param data:
        @return: 新的 md5，md5 是否有变化
        """
        md5 = compute_pipeline_md5(data)
        return md5, self.md5sum != md5


class BaseSecretField:
    """
    Secret字段：入库加密， 出库解密
    """

    _crypt = BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    def from_db_value(self, value, expression, connection):
        if not value:
            return None
        return self._crypt.decrypt(value)

    def to_python(self, value):
        if value is None:
            return value
        return self._crypt.encrypt(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return self._crypt.encrypt(value)


class SecretField(BaseSecretField, models.CharField):
    """
    Secret字段：入库加密， 出库解密
    """

    def from_db_value(self, value, expression, connection):
        return super().from_db_value(value, expression, connection)

    def to_python(self, value):
        return super().to_python(value)

    def get_prep_value(self, value):
        return super().get_prep_value(value)


class SecretTextField(BaseSecretField, models.TextField):
    """
    Secret字段：入库加密， 出库解密
    """

    def from_db_value(self, value, expression, connection):
        return super().from_db_value(value, expression, connection)

    def to_python(self, value):
        return super().to_python(value)

    def get_prep_value(self, value):
        return super().get_prep_value(value)


class SecretSingleJsonField(models.JSONField):
    """
    Secret JSON 字段：只支持单层 JSON 结构，对每个 key 的 value 进行加密/解密

    示例：
        {"username": "admin", "password": "secret123"}
        存储时：{"username": "encrypted_admin", "password": "encrypted_secret123"}
    """

    _crypt = BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    def from_db_value(self, value, expression, connection):
        """
        从数据库读取时，解密 JSON 中所有 value

        :param value: 数据库中的加密 JSON 数据
        :param expression: 查询表达式
        :param connection: 数据库连接
        :return: 解密后的 JSON 数据
        """
        if not value:
            return value

        # 先调用父类方法获取 JSON 对象
        value = super().from_db_value(value, expression, connection)

        if not isinstance(value, dict):
            return value

        # 解密每个 value
        decrypted_data = {}
        for key, val in value.items():
            if val is not None:
                try:
                    decrypted_data[key] = self._crypt.decrypt(val)
                except Exception:
                    # 如果解密失败，返回原值（可能是未加密的旧数据）
                    decrypted_data[key] = val
            else:
                decrypted_data[key] = val

        return decrypted_data

    def get_prep_value(self, value):
        """
        写入数据库时，加密 JSON 中所有 value

        :param value: 原始 JSON 数据
        :return: 加密后的 JSON 数据
        """
        if value is None:
            return value

        if not isinstance(value, dict):
            raise ValueError("SecretSingleJsonField 只支持字典类型的数据")

        # 检查是否为单层 JSON
        for key, val in value.items():
            if isinstance(val, (dict, list)):
                raise ValueError("SecretSingleJsonField 只支持单层 JSON 结构，不支持嵌套对象或数组")

        # 加密每个 value
        encrypted_data = {}
        for key, val in value.items():
            if val is not None and isinstance(val, str):
                encrypted_data[key] = self._crypt.encrypt(val)
            else:
                encrypted_data[key] = val

        # 调用父类方法处理 JSON 序列化
        return super().get_prep_value(encrypted_data)
