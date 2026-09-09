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
from unittest.mock import MagicMock, Mock, patch

from bamboo_engine.eri import ContextValue, ContextValueType
from django.test import TestCase
from pipeline.component_framework.test import (
    Call,
    CallAssertion,
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    Patcher,
)

from bkflow.pipeline_plugins.components.collections.python_code.executor import (
    ERROR_PHASE_EXECUTOR,
    PythonCodeExecutionResult,
)
from bkflow.pipeline_plugins.components.collections.python_code.v1_0_0 import (
    PythonCodeComponent,
    PythonCodeService,
)


class PythonCodeComponentTest(TestCase, ComponentTestMixin):
    def setUp(self):
        PythonCodeService.top_pipeline_id = "test_pipeline_id"
        # 默认关闭trace开关
        self.trace_patcher = patch("django.conf.settings.ENABLE_OTEL_TRACE", False)
        self.trace_patcher.start()
        super().setUp()

    def tearDown(self):
        self.trace_patcher.stop()
        super().tearDown()

    def component_cls(self):
        return PythonCodeComponent

    def cases(self):
        return [
            SIMPLE_RETURN_CASE,
            WITH_ARGUMENTS_CASE,
            WITH_VARIABLE_RENDERING_CASE,
            WITH_MIXED_VARIABLE_CASE,
            SYNTAX_ERROR_CASE,
            RUNTIME_ERROR_CASE,
            NO_MAIN_FUNCTION_CASE,
            INVALID_SIGNATURE_CASE,
            COMPLEX_LOGIC_CASE,
            EXECUTOR_ERROR_CASE,
            SELECTED_OUTPUT_CASE,
            SELECTED_EMPTY_OUTPUT_CASE,
            MISSING_OUTPUT_KEY_CASE,
        ]


# ==================== Mock Runtime ====================

BAMBOO_RUNTIME_CLASS = "bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.BambooDjangoRuntime"


class MockContextClient:
    def __init__(self, get_context_values):
        self.get_context_values = MagicMock(return_value=get_context_values)


# ==================== Test Case 1: Simple Return ====================

SIMPLE_CODE = """
def main(arg1: str, arg2: str):
    return {"result": arg1 + arg2}
"""

SIMPLE_INPUT_VARS = {"arg1": "Hello, ", "arg2": "World!"}

SIMPLE_RETURN_CASE = ComponentTestCase(
    name="simple_return_case",
    inputs={"bk_python_code": SIMPLE_CODE, "bk_input_vars": SIMPLE_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(success=True, outputs={"output": {"result": "Hello, World!"}, "error": ""}),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 2: With Arguments ====================

WITH_ARGS_CODE = """
def main(x: int, y: int):
    return {
        "sum": x + y,
        "product": x * y,
        "difference": x - y
    }
"""

WITH_ARGS_INPUT_VARS = {"x": 10, "y": 5}

WITH_ARGUMENTS_CASE = ComponentTestCase(
    name="with_arguments_case",
    inputs={"bk_python_code": WITH_ARGS_CODE, "bk_input_vars": WITH_ARGS_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=True, outputs={"output": {"sum": 15, "product": 50, "difference": 5}, "error": ""}
    ),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 3: With Variable Rendering ====================

VARIABLE_RENDERING_CODE = """
def main(data1: str, data2: int):
    # 使用 str(type()) 获取类型名称，避免访问 __name__ 属性
    type_map = {str: "str", int: "int", float: "float", bool: "bool", list: "list", dict: "dict"}
    data1_type = type_map.get(type(data1), "unknown")
    data2_type = type_map.get(type(data2), "unknown")
    return {
        "data1_type": data1_type,
        "data2_type": data2_type,
        "data1_value": data1,
        "data2_value": data2
    }
"""

VARIABLE_RENDERING_INPUT_VARS = {"data1": "${workflow_var1}", "data2": "${workflow_var2}"}

VARIABLE_RENDERING_CONTEXT_VALUES = [
    ContextValue(key="workflow_var1", type=ContextValueType.PLAIN, value="test_string", code=None),
    ContextValue(key="workflow_var2", type=ContextValueType.PLAIN, value=42, code=None),
]

VARIABLE_RENDERING_CLIENT = MockContextClient(get_context_values=VARIABLE_RENDERING_CONTEXT_VALUES)

WITH_VARIABLE_RENDERING_CASE = ComponentTestCase(
    name="with_variable_rendering_case",
    inputs={"bk_python_code": VARIABLE_RENDERING_CODE, "bk_input_vars": VARIABLE_RENDERING_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={
            "output": {
                "data1_type": "str",
                "data2_type": "int",
                "data1_value": "test_string",
                "data2_value": 42,
            },
            "error": "",
        },
    ),
    execute_call_assertion=[
        CallAssertion(
            func=VARIABLE_RENDERING_CLIENT.get_context_values,
            calls=[Call(pipeline_id="test_pipeline_id", keys={"workflow_var1", "workflow_var2"})],
        )
    ],
    schedule_assertion=None,
    patchers=[Patcher(target=BAMBOO_RUNTIME_CLASS, return_value=VARIABLE_RENDERING_CLIENT)],
)


# ==================== Test Case 4: Mixed Variable and Direct Value ====================

MIXED_VARIABLE_CODE = """
def main(var_value: str, direct_value: str):
    return {
        "combined": var_value + " " + direct_value
    }
"""

MIXED_VARIABLE_INPUT_VARS = {"var_value": "${my_var}", "direct_value": "direct_string"}

MIXED_VARIABLE_CONTEXT_VALUES = [
    ContextValue(key="my_var", type=ContextValueType.PLAIN, value="from_workflow", code=None)
]

MIXED_VARIABLE_CLIENT = MockContextClient(get_context_values=MIXED_VARIABLE_CONTEXT_VALUES)

WITH_MIXED_VARIABLE_CASE = ComponentTestCase(
    name="with_mixed_variable_case",
    inputs={"bk_python_code": MIXED_VARIABLE_CODE, "bk_input_vars": MIXED_VARIABLE_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=True, outputs={"output": {"combined": "from_workflow direct_string"}, "error": ""}
    ),
    execute_call_assertion=[
        CallAssertion(
            func=MIXED_VARIABLE_CLIENT.get_context_values,
            calls=[Call(pipeline_id="test_pipeline_id", keys={"my_var"})],
        )
    ],
    schedule_assertion=None,
    patchers=[Patcher(target=BAMBOO_RUNTIME_CLASS, return_value=MIXED_VARIABLE_CLIENT)],
)


# ==================== Test Case 5: Syntax Error ====================

SYNTAX_ERROR_CODE = """
def main(arg1):
    return {
        "result": arg1 +   # 语法错误：不完整的表达式
"""

SYNTAX_ERROR_CASE = ComponentTestCase(
    name="syntax_error_case",
    inputs={"bk_python_code": SYNTAX_ERROR_CODE, "bk_input_vars": {"arg1": "test"}},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={
            "ex_data": "执行器错误: ('Line 4: SyntaxError: unexpected EOF "
            "while parsing at statement: \\'\"result\": arg1 +   # 语法错误：不完整的表达式\\'',)"
        },
    ),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 6: Runtime Error ====================

RUNTIME_ERROR_CODE = """
def main(arg1: int):
    result = arg1 / 0  # 运行时错误：除以零
    return {"result": result}
"""

RUNTIME_ERROR_CASE = ComponentTestCase(
    name="runtime_error_case",
    inputs={"bk_python_code": RUNTIME_ERROR_CODE, "bk_input_vars": {"arg1": 10}},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False, outputs={"output": {}, "error": "执行错误: division by zero", "ex_data": "执行错误: division by zero"}
    ),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 7: No Main Function ====================

NO_MAIN_FUNCTION_CODE = """
def helper_function():
    return "I am not main"
"""

NO_MAIN_FUNCTION_CASE = ComponentTestCase(
    name="no_main_function_case",
    inputs={"bk_python_code": NO_MAIN_FUNCTION_CODE, "bk_input_vars": {}},
    parent_data={},
    execute_assertion=ExecuteAssertion(success=False, outputs={"ex_data": "编译错误: 代码中必须定义main函数"}),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 8: Invalid Signature ====================

INVALID_SIGNATURE_CODE = """
def main(arg1: str):
    return {"result": arg1}
"""

INVALID_SIGNATURE_INPUT_VARS = {
    "arg1": "test",
    "arg2": "extra",  # main函数只接受arg1，但传入了arg2
}

INVALID_SIGNATURE_CASE = ComponentTestCase(
    name="invalid_signature_case",
    inputs={"bk_python_code": INVALID_SIGNATURE_CODE, "bk_input_vars": INVALID_SIGNATURE_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={
            "output": {},
            "error": "执行错误: main() got an unexpected keyword argument 'arg2'",
            "ex_data": "执行错误: main() got an unexpected keyword argument 'arg2'",
        },
    ),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 9: Complex Logic ====================

COMPLEX_LOGIC_CODE = """
def main(numbers: list):
    if not numbers:
        return {"error": "Empty list"}

    total = sum(numbers)
    avg = total / len(numbers)
    max_val = max(numbers)
    min_val = min(numbers)

    sorted_nums = sorted(numbers)

    return {
        "total": total,
        "average": avg,
        "max": max_val,
        "min": min_val,
        "sorted": sorted_nums,
        "count": len(numbers)
    }
"""

COMPLEX_LOGIC_INPUT_VARS = {"numbers": [5, 2, 8, 1, 9, 3]}

COMPLEX_LOGIC_CASE = ComponentTestCase(
    name="complex_logic_case",
    inputs={"bk_python_code": COMPLEX_LOGIC_CODE, "bk_input_vars": COMPLEX_LOGIC_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={
            "output": {
                "total": 28,
                "average": 28 / 6,
                "max": 9,
                "min": 1,
                "sorted": [1, 2, 3, 5, 8, 9],
                "count": 6,
            },
            "error": "",
        },
    ),
    schedule_assertion=None,
    patchers=[],
)


# ==================== Test Case 10: Executor Error ====================

EXECUTOR_ERROR_MESSAGE = "执行器错误: 子进程异常退出（-9）"
EXECUTOR_ERROR_CASE = ComponentTestCase(
    name="executor_error_case",
    inputs={"bk_python_code": SIMPLE_CODE, "bk_input_vars": SIMPLE_INPUT_VARS},
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={"output": {}, "error": EXECUTOR_ERROR_MESSAGE, "ex_data": EXECUTOR_ERROR_MESSAGE},
    ),
    schedule_assertion=None,
    patchers=[
        Patcher(
            target="bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.PythonCodeExecutor.execute_code",
            return_value=PythonCodeExecutionResult(
                False,
                None,
                EXECUTOR_ERROR_MESSAGE,
                ERROR_PHASE_EXECUTOR,
            ),
        )
    ],
)


SELECTED_OUTPUT_CASE = ComponentTestCase(
    name="selected_output_skips_unserializable_field",
    inputs={
        "bk_python_code": "def main():\n    return {'selected': 'ok', 'scratch': itertools.count()}",
        "bk_output_key": "selected",
    },
    parent_data={},
    execute_assertion=ExecuteAssertion(success=True, outputs={"output": "ok", "error": ""}),
    schedule_assertion=None,
    patchers=[],
)

SELECTED_EMPTY_OUTPUT_CASE = ComponentTestCase(
    name="selected_empty_output_is_preserved",
    inputs={"bk_python_code": "def main():\n    return {'selected': {}}", "bk_output_key": "selected"},
    parent_data={},
    execute_assertion=ExecuteAssertion(success=True, outputs={"output": {}, "error": ""}),
    schedule_assertion=None,
    patchers=[],
)

MISSING_OUTPUT_KEY_ERROR = "输出key 'missing' 不存在于main函数返回的字典中"
MISSING_OUTPUT_KEY_CASE = ComponentTestCase(
    name="missing_output_key_sets_failure_outputs",
    inputs={
        "bk_python_code": "def main():\n    return {'scratch': itertools.count()}",
        "bk_output_key": "missing",
    },
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={"output": {}, "error": MISSING_OUTPUT_KEY_ERROR, "ex_data": MISSING_OUTPUT_KEY_ERROR},
    ),
    schedule_assertion=None,
    patchers=[],
)


def test_large_result_log_is_bounded_without_changing_output(caplog):
    """大字符串和嵌套大结果仍完整输出，但成功日志不能包含完整内容。"""
    service = PythonCodeService()
    service.logger = logging.getLogger("python_code_bounded_log")
    for code in ["'x' * (11 * 1024 * 1024)", "{'payload': ['x' * (1024 * 1024)]}", "range(10 ** 100)"]:
        data = Mock()
        outputs = {}
        data.set_outputs.side_effect = outputs.__setitem__
        inputs = {"bk_python_code": "def main():\n    return " + code}
        data.get_one_of_inputs.side_effect = inputs.get
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=service.logger.name):
            assert service.plugin_execute(data, None) is True
        message = next(record.getMessage() for record in caplog.records if "main函数执行成功" in record.getMessage())
        assert len(message) < 1024
        assert "x" * 1024 not in message
        assert outputs["error"] == ""
        if isinstance(outputs["output"], str):
            assert len(outputs["output"]) == 11 * 1024 * 1024
        elif isinstance(outputs["output"], dict):
            assert len(outputs["output"]["payload"][0]) == 1024 * 1024
        else:
            assert outputs["output"].stop == 10**100
