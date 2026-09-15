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

import collections
import re
import threading
from typing import Any, Dict

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from pipeline.component_framework.component import Component
from pipeline.core.flow.io import ObjectItemSchema, StringItemSchema
from pipeline.eri.runtime import BambooDjangoRuntime

from bkflow.pipeline_plugins.components.collections.base import BKFlowBaseService
from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    ERROR_PHASE_COMPILE,
    PythonCodeExecutor,
)

__group_name__ = _("蓝鲸服务(BK)")

DEFAULT_TIMEOUT = getattr(settings, "PYTHON_CODE_PLUGIN_TIMEOUT", 30)
QUEUE_TIMEOUT = getattr(settings, "PYTHON_CODE_PLUGIN_QUEUE_TIMEOUT", DEFAULT_TIMEOUT)
MAX_CODE_LENGTH = getattr(settings, "PYTHON_CODE_PLUGIN_MAX_LENGTH", 10240)
DEFAULT_MEMORY_LIMIT_MB = getattr(settings, "PYTHON_CODE_PLUGIN_MEMORY_LIMIT_MB", 256)
MAX_CONCURRENT_PROCESSES = max(1, int(getattr(settings, "PYTHON_CODE_PLUGIN_MAX_CONCURRENT_PROCESSES", 4)))
MAX_RESPONSE_SIZE_BYTES = max(0, int(getattr(settings, "PYTHON_CODE_PLUGIN_MAX_RESPONSE_SIZE_BYTES", 0)))
PYTHON_CODE_PROCESS_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_PROCESSES)


class PythonCodeService(BKFlowBaseService):
    """Python代码执行服务"""

    plugin_name = "python_code"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executor = PythonCodeExecutor(
            service=self,
            timeout=DEFAULT_TIMEOUT,
            max_code_length=MAX_CODE_LENGTH,
            memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB,
            max_response_size_bytes=MAX_RESPONSE_SIZE_BYTES,
            process_semaphore=PYTHON_CODE_PROCESS_SEMAPHORE,
            queue_timeout=QUEUE_TIMEOUT,
        )

    def inputs_format(self):
        return [
            self.InputItem(
                name=_("Python代码"),
                key="bk_python_code",
                type="string",
                schema=StringItemSchema(description=_("请输入包含main函数的Python代码。\n" "main函数签名可以根据实际需要自定义参数。")),
            ),
            self.InputItem(
                name=_("输入变量"),
                key="bk_input_vars",
                type="object",
                schema=ObjectItemSchema(
                    property_schemas={},
                    description=_("配置main函数的输入参数。\n" "key为参数名，value为对应的值（支持变量引用）"),
                ),
            ),
        ]

    def outputs_format(self):
        return [
            self.OutputItem(
                name=_("执行结果"),
                key="output",
                type="object",
                schema=ObjectItemSchema(
                    property_schemas={},
                    description=_("main函数的返回结果"),
                ),
            ),
            self.OutputItem(
                name=_("错误信息"),
                key="error",
                type="string",
                schema=StringItemSchema(description=_("执行错误信息，正常执行时为空字符串")),
            ),
        ]

    def plugin_execute(self, data, parent_data):
        """执行Python代码"""
        python_code = data.get_one_of_inputs("bk_python_code")
        input_vars_config = data.get_one_of_inputs("bk_input_vars") or {}
        output_key = data.get_one_of_inputs("bk_output_key") or ""

        if not python_code:
            error_msg = "Python代码不能为空"
            self.logger.error(error_msg)
            data.outputs.ex_data = error_msg
            return False

        input_args = {}
        if input_vars_config:
            try:
                input_args = self._get_input_args(parent_data, input_vars_config)
            except Exception as e:
                error_msg = f"获取输入变量失败: {str(e)}"
                self.logger.exception(error_msg)
                data.outputs.ex_data = error_msg
                return False

        self.logger.info(f"执行main函数，输入参数: {list(input_args.keys())}")

        try:
            execution_result = self.executor.execute_code(python_code, input_args=input_args, output_key=output_key)
            success, result, output_info = execution_result
        except Exception as e:
            error_msg = f"执行器异常: {str(e)}"
            self.logger.exception(error_msg)
            data.set_outputs("output", {})
            data.set_outputs("error", error_msg)
            data.outputs.ex_data = error_msg
            return False

        if not success:
            error_msg = output_info or "执行失败"
            if execution_result.error_phase == ERROR_PHASE_COMPILE:
                self.logger.error(f"Python代码编译失败: {error_msg}")
                data.outputs.ex_data = error_msg
                return False

            self.logger.error(f"main函数执行失败: {error_msg}")
            data.set_outputs("output", {})
            data.set_outputs("error", error_msg)
            data.outputs.ex_data = error_msg
            return False

        data.set_outputs("output", result)
        data.set_outputs("error", "")
        self.logger.info("main函数执行成功，结果摘要: %s", self._summarize_result(result))
        return True

    @staticmethod
    def _summarize_result(result: Any) -> str:
        """只查看类型、长度及文本前缀，避免完整 repr 造成额外大对象和日志。"""
        summary = f"type={type(result).__name__}"
        if isinstance(result, (str, bytes, bytearray, dict, list, tuple, set, frozenset, range, collections.deque)):
            try:
                summary += f", length={len(result)}"
            except OverflowError:
                summary += ", length=overflow"
        if isinstance(result, (str, bytes, bytearray)):
            summary += f", preview={result[:128]!r}"
            if len(result) > 128:
                summary += "..."
        return summary

    def _get_input_args(self, parent_data, input_vars_config: dict) -> Dict[str, Any]:
        """获取main函数的输入参数

        Args:
            parent_data: 父数据
            input_vars_config: 输入变量配置，格式为 {"arg1": "value1", "arg2": "${var1}"}

        Returns:
            main函数的输入参数字典
        """
        runtime = BambooDjangoRuntime()
        pipeline_id = self.top_pipeline_id

        var_pattern = re.compile(r"\$\{(\w+)\}")
        workflow_var_keys = set()

        for value in input_vars_config.values():
            if isinstance(value, str):
                matches = var_pattern.findall(value)
                for var_name in matches:
                    workflow_var_keys.add(var_name)

        if not workflow_var_keys:
            return input_vars_config

        try:
            context_values = runtime.get_context_values(pipeline_id=pipeline_id, keys=workflow_var_keys)
        except Exception as e:
            self.logger.warning(f"获取上下文变量失败: {e}")
            return input_vars_config

        context_dict = {}
        for cv in context_values:
            context_dict[cv.key] = cv.value

        input_args = {}
        for param_key, value in input_vars_config.items():
            if isinstance(value, str) and "${" in value:
                rendered_value = value
                for var_name, var_value in context_dict.items():
                    var_ref = f"${{{var_name}}}"
                    if var_ref in rendered_value:
                        if rendered_value == var_ref:
                            rendered_value = var_value
                            break
                        rendered_value = rendered_value.replace(var_ref, str(var_value))
                input_args[param_key] = rendered_value
            else:
                input_args[param_key] = value

        return input_args


class PythonCodeComponent(Component):
    name = _("Python代码")
    code = "python_code"
    bound_service = PythonCodeService
    form = settings.STATIC_URL + "components/python_code/v1_0_0.js"
    version = "v1.0.0"
    desc = _(
        "在受控环境中安全执行Python代码\n"
        "使用：定义main函数，通过输入变量配置映射工作流变量到main参数\n"
        "限制：禁止导入危险模块(os/sys/subprocess等)和使用eval/exec等危险函数\n\n"
        "支持内置模块：json_dumps, json_loads, math, statistics, decimal, fractions, datetime"
        ", collections, itertools, functools, string, textwrap, base64, hashlib, hmac, uuid, copy\n"
        "支持第三方模块：jsonschema\n\n"
        "示例：\n"
        "def main(arg1: str, arg2: str):\n"
        '&nbsp;&nbsp;&nbsp;&nbsp;return {"result": arg1 + arg2}'
    )
