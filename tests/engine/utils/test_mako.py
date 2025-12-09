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
import pytest

from bkflow.utils.mako import parse_mako_expression


class TestMakoUtils:
    """Test mako expression parsing"""

    def test_parse_true_expression(self):
        """Test parsing expression that evaluates to True"""
        result = parse_mako_expression("${1 == 1}", {})
        assert result is True

    def test_parse_false_expression(self):
        """Test parsing expression that evaluates to False"""
        result = parse_mako_expression("${1 == 2}", {})
        assert result is False

    def test_parse_with_context(self):
        """Test parsing with context variables"""
        context = {"x": 10, "y": 5}
        result = parse_mako_expression("${x > y}", context)
        assert result is True

    def test_parse_complex_expression(self):
        """Test complex boolean expression"""
        context = {"a": 10, "b": 20, "c": 15}
        result = parse_mako_expression("${a < c and c < b}", context)
        assert result is True

    def test_parse_invalid_result(self):
        """Test that non-boolean result raises ValueError"""
        with pytest.raises(ValueError, match="must be a boolean"):
            parse_mako_expression("${1 + 1}", {})

    def test_parse_string_result(self):
        """Test that string result raises ValueError"""
        with pytest.raises(ValueError, match="must be a boolean"):
            parse_mako_expression("${'hello'}", {})
