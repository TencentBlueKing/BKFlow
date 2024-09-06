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
from bkflow_dmn.api import decide_single_table
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ObjectItemSchema

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.decision_table.table_parser import DecisionTableParser
from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService

__group_name__ = _("蓝鲸服务(BK)")

from bkflow.utils.handlers import handle_plain_log


class DmnPluginService(BKFlowBaseService):
    def inputs_format(self):
        return [
            self.InputItem(
                name=_("决策表"),
                key="decision_table",
                type="object",
                schema=ObjectItemSchema(description=_("决策表"), property_schemas={}),
            ),
            self.InputItem(
                name=_("决策表 facts"),
                key="facts",
                type="object",
                schema=ObjectItemSchema(description=_("决策表 facts"), property_schemas={}),
            ),
        ]

    def outputs_format(self):
        return []

    def plugin_execute(self, data, parent_data):
        space_id = parent_data.get_one_of_inputs("task_space_id")
        table_id = data.get_one_of_inputs("table_id")
        raw_facts = data.get_one_of_inputs("facts")
        facts = {fact_id: fact["value"] for fact_id, fact in raw_facts.items()}

        # 获取决策表数据
        interface_client = InterfaceModuleClient()
        result = interface_client.get_decision_table(decision_table_id=table_id, data={"space_id": space_id})
        if not result["result"]:
            message = handle_plain_log("[get decision table] error: {}".format(result["message"]))
            self.logger.error(message)
            data.outputs.ex_data = message
            return False

        table = result["data"]
        try:
            parser = DecisionTableParser(title=table["name"], decision_table=table["data"])
            decision_table = parser.parse()
            self.logger.info(f"parsed decision table: {decision_table}")
            table_outputs = decide_single_table(decision_table, facts)
        except Exception as e:
            self.logger.exception(f"decision_table: {table['data']}, facts: {facts}, error: {e}")
            data.set_outputs("ex_data", e)
            return False

        self.logger.info(f"match outputs: {table_outputs}")

        if len(table_outputs) != 1:
            data.set_outputs("ex_data", f"please confirm only one row matched, current outputs: {table_outputs}")
            return False

        for output_field_id, output_value in table_outputs[0].items():
            data.set_outputs(output_field_id, output_value)
        return True


class DmnPluginComponent(Component):
    name = _("决策插件")
    code = "dmn_plugin"
    bound_service = DmnPluginService
    form = settings.STATIC_URL + "components/dmn_plugin/v1_0_0.js"
    version = "v1.0.0"
    desc = "提供决策计算能力，可将输出用于分支网关简化流程设计"
