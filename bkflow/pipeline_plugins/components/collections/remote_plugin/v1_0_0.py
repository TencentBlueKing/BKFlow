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

from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import StringItemSchema

from bkflow.pipeline_plugins.components.collections.base import (
    BKFlowBaseService,
    StepIntervalGenerator,
)
from plugin_service.conf import PLUGIN_LOGGER
from plugin_service.exceptions import PluginServiceException
from plugin_service.plugin_client import PluginServiceApiClient

logger = logging.getLogger(PLUGIN_LOGGER)


class State:
    EMPTY = 1
    POLL = 2
    CALLBACK = 3
    SUCCESS = 4
    FAIL = 5


UNFINISHED_STATES = {State.POLL, State.CALLBACK}


class RemotePluginService(BKFlowBaseService):
    interval = StepIntervalGenerator()

    def outputs_format(self):
        return [
            self.OutputItem(
                name="Trace ID", key="trace_id", type="string", schema=StringItemSchema(description="Trace ID")
            ),
        ]

    def plugin_execute(self, data, parent_data):
        plugin_code = data.get_one_of_inputs("plugin_code")
        plugin_version = data.get_one_of_inputs("plugin_version")
        space_id = parent_data.get_one_of_inputs("task_space_id")

        try:
            plugin_client = PluginServiceApiClient(plugin_code)
        except PluginServiceException as e:
            message = _(f"第三方插件client初始化失败, 错误内容: {e}")
            logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        detail_result = plugin_client.get_detail(plugin_version)
        if not detail_result["result"]:
            message = _("获取第三方插件详情失败, 错误内容: {message}").format(message=detail_result["message"])
            logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        plugin_context = dict(
            [
                (key, parent_data.inputs[key])
                for key in detail_result["data"]["context_inputs"]["properties"].keys()
                if key in parent_data.inputs
            ]
        )
        ok, result_data = plugin_client.invoke(
            plugin_version,
            {"inputs": data.inputs, "context": plugin_context},
            extra_headers={"Bkplugin-Scope-Type": "space", "Bkplugin-Scope-Value": str(space_id)},
        )
        if not ok:
            message = _("调用第三方插件invoke接口错误, 错误内容: {message}, trace_id: {trace_id}").format(
                message=detail_result["message"], trace_id=result_data.get("trace_id")
            )
            logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        data.set_outputs("trace_id", result_data["trace_id"])
        self._inject_result_data_outputs(data, result_data)

        state = result_data["state"]
        if state == State.FAIL:
            data.set_outputs("ex_data", result_data["err"])
            return False
        if state in UNFINISHED_STATES:
            setattr(self, "__need_schedule__", True)
        return True

    def plugin_schedule(self, data, parent_data, callback_data=None):
        plugin_code = data.get_one_of_inputs("plugin_code")
        trace_id = data.get_one_of_outputs("trace_id")

        if self.interval.reach_limit():
            data.set_outputs(
                "ex_data", message="reach max count of schedule, please ensure the task can be finished in one day"
            )
            return False

        try:
            plugin_client = PluginServiceApiClient(plugin_code)
        except PluginServiceException as e:
            message = _(f"第三方插件client初始化失败, 错误内容: {e}")
            logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        ok, result_data = plugin_client.get_schedule(trace_id)

        if not ok:
            message = (
                f"remote plugin service schedule error: {result_data['message']}, "
                f"trace_id: {result_data.get('trace_id') or trace_id}"
            )
            logger.error(message)
            data.set_outputs("ex_data", message)
            return False

        self._inject_result_data_outputs(data, result_data)

        state = result_data["state"]
        if state == State.FAIL:
            message = _("请通过第三方节点日志查看任务失败原因")
            logger.error(message)
            logger.error(f"[remote plugin service state failed]: {result_data}")
            data.set_outputs("ex_data", result_data["outputs"].get("err") or message)
            return False
        if state in UNFINISHED_STATES:
            setattr(self, "__need_schedule__", True)
        if state == State.SUCCESS:
            self.finish_schedule()
        return True

    @staticmethod
    def _inject_result_data_outputs(data, result_data):
        outputs = result_data.get("outputs") or {}
        for key, output in outputs.items():
            data.set_outputs(key, output)


class RemotePluginComponent(Component):
    code = "remote_plugin"
    name = "RemotePlugin"
    bound_service = RemotePluginService
    version = "1.0.0"
