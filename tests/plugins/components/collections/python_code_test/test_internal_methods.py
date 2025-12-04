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

from unittest.mock import MagicMock, Mock, patch

from bamboo_engine.eri import ContextValue, ContextValueType
from django.test import TestCase

from bkflow.pipeline_plugins.components.collections.python_code.v1_0_0 import (
    PythonCodeService,
)


class PythonCodeServiceInternalMethodsTest(TestCase):
    """测试 PythonCodeService 的公共方法"""

    def setUp(self):
        self.service = PythonCodeService()
        self.service.top_pipeline_id = "test_pipeline_id"
        self.service.logger = Mock()

    def test_get_input_args_with_direct_values(self):
        """测试获取输入参数 - 直接值"""
        input_vars_config = {"arg1": "hello", "arg2": 42, "arg3": True}

        result = self.service._get_input_args(None, input_vars_config)

        assert result == {"arg1": "hello", "arg2": 42, "arg3": True}

    @patch("bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.BambooDjangoRuntime")
    def test_get_input_args_with_variable_references(self, mock_runtime_class):
        """测试获取输入参数 - 变量引用"""
        # Mock runtime
        mock_runtime = MagicMock()
        mock_runtime.get_context_values.return_value = [
            ContextValue(key="var1", type=ContextValueType.PLAIN, value="value1", code=None),
            ContextValue(key="var2", type=ContextValueType.PLAIN, value=100, code=None),
        ]
        mock_runtime_class.return_value = mock_runtime

        input_vars_config = {"arg1": "${var1}", "arg2": "${var2}", "arg3": "direct"}

        result = self.service._get_input_args(None, input_vars_config)

        # 验证变量被正确解析
        assert result["arg1"] == "value1"
        assert result["arg2"] == 100
        assert result["arg3"] == "direct"

        # 验证调用了 get_context_values
        mock_runtime.get_context_values.assert_called_once_with(pipeline_id="test_pipeline_id", keys={"var1", "var2"})

    @patch("bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.BambooDjangoRuntime")
    def test_get_input_args_with_string_interpolation(self, mock_runtime_class):
        """测试获取输入参数 - 字符串插值"""
        # Mock runtime
        mock_runtime = MagicMock()
        mock_runtime.get_context_values.return_value = [
            ContextValue(key="name", type=ContextValueType.PLAIN, value="Alice", code=None),
            ContextValue(key="age", type=ContextValueType.PLAIN, value=30, code=None),
        ]
        mock_runtime_class.return_value = mock_runtime

        input_vars_config = {"message": "Hello ${name}, you are ${age} years old"}

        result = self.service._get_input_args(None, input_vars_config)

        # 验证字符串插值
        assert result["message"] == "Hello Alice, you are 30 years old"

    @patch("bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.BambooDjangoRuntime")
    def test_get_input_args_with_missing_variable(self, mock_runtime_class):
        """测试获取输入参数 - 变量不存在"""
        # Mock runtime 返回空列表（变量不存在）
        mock_runtime = MagicMock()
        mock_runtime.get_context_values.return_value = []
        mock_runtime_class.return_value = mock_runtime

        input_vars_config = {"arg1": "${missing_var}"}

        result = self.service._get_input_args(None, input_vars_config)

        # 验证保留原始值
        assert result["arg1"] == "${missing_var}"

    @patch("bkflow.pipeline_plugins.components.collections.python_code.v1_0_0.BambooDjangoRuntime")
    def test_get_input_args_runtime_exception(self, mock_runtime_class):
        """测试获取输入参数 - Runtime 异常"""
        # Mock runtime 抛出异常
        mock_runtime = MagicMock()
        mock_runtime.get_context_values.side_effect = Exception("Runtime error")
        mock_runtime_class.return_value = mock_runtime

        input_vars_config = {"arg1": "${var1}"}

        result = self.service._get_input_args(None, input_vars_config)

        # 验证异常被捕获，返回原始配置
        assert result == {"arg1": "${var1}"}
        self.service.logger.warning.assert_called()

    def test_get_input_args_empty_config(self):
        """测试获取输入参数 - 空配置"""
        input_vars_config = {}

        result = self.service._get_input_args(None, input_vars_config)

        assert result == {}

    def test_inputs_format(self):
        """测试输入格式定义"""
        inputs = self.service.inputs_format()

        # 验证有两个输入项
        assert len(inputs) == 2

        # 验证 bk_python_code
        code_input = next((item for item in inputs if item.key == "bk_python_code"), None)
        assert code_input is not None
        assert code_input.type == "string"
        assert code_input.name

        # 验证 bk_input_vars
        vars_input = next((item for item in inputs if item.key == "bk_input_vars"), None)
        assert vars_input is not None
        assert vars_input.type == "object"
        assert vars_input.name

    def test_outputs_format(self):
        """测试输出格式定义"""
        outputs = self.service.outputs_format()

        # 验证有两个输出项
        assert len(outputs) == 2

        # 验证 output
        output_item = next((item for item in outputs if item.key == "output"), None)
        assert output_item is not None
        assert output_item.type == "object"
        assert output_item.name

        # 验证 error
        error_item = next((item for item in outputs if item.key == "error"), None)
        assert error_item is not None
        assert error_item.type == "string"
        assert error_item.name
