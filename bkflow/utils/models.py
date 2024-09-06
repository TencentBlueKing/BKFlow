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
import hashlib
import json

from django.db import models
from django.utils.translation import ugettext_lazy as _
from pipeline.models import CompressJSONField, SnapshotManager

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
        super(CommonModel, self).delete()


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
