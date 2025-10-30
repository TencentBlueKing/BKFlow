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

from django.db import models
from pipeline.core.constants import PE

from bkflow.pipeline_plugins.components.collections.dmn_plugin.v1_0_0 import (
    DmnPluginComponent,
)
from bkflow.template.models import Template
from bkflow.utils.models import CommonModel

logger = logging.getLogger(__name__)


class DecisionTableManager(models.Manager):
    pass


class DecisionTable(CommonModel):
    TABLE_TYPES = (("single", "single"), ("multi", "multi"))

    name = models.CharField("decision table name", max_length=64)
    desc = models.CharField("decision table description", max_length=256, default="", null=True, blank=True)
    space_id = models.IntegerField("space ID", db_index=True)
    template_id = models.BigIntegerField(verbose_name="template ID", null=True, blank=True, db_index=True)
    scope_type = models.CharField("scope type of decision table", max_length=128, null=True, blank=True)
    scope_value = models.CharField("scope value of decision table", max_length=128, null=True, blank=True)
    data = models.JSONField("data of decision table")
    table_type = models.CharField("table type", max_length=32, choices=TABLE_TYPES, default="single")
    extra_info = models.JSONField("extra info", default=dict)

    objects = DecisionTableManager()

    class Meta:
        verbose_name = "Decision Table"
        index_together = [("space_id", "scope_type", "scope_value")]
        ordering = ["-id"]

    def check_used_by_template(self) -> (bool, list):
        """检查决策表有没有被流程引用"""
        template = Template.objects.filter(id=self.template_id).first()
        if not template:
            raise ValueError(f"Template {self.template_id} does not exist")

        try:
            matched_node_ids = []
            for node in template.pipeline_tree[PE.activities].values():
                if node["type"] == "SubProcess":
                    continue
                if (
                    node["component"]["code"] == DmnPluginComponent.code
                    and node["component"]["data"]["table_id"]["value"] == self.id
                ):
                    matched_node_ids.append(node["id"])
        except KeyError as e:
            msg = f"template {template.id} nodes parsing error: {e}"
            logger.exception(msg)
            raise ValueError(msg)

        return (True, matched_node_ids) if matched_node_ids else (False, [])
