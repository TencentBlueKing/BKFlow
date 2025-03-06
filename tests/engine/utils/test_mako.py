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
import pytest

from bkflow.utils.mako import parse_mako_expression


class TestParseMakoExpression:
    def test_parse_mako_expression_without_context_true(self):
        expression = "${1 == 1}"
        context = {}
        assert parse_mako_expression(expression, context) is True

    def test_parse_mako_expression_with_context_true(self):
        expression = "${a == 2}"
        context = {"a": 2}
        assert parse_mako_expression(expression, context) is True

    def test_parse_mako_expression_without_context_false(self):
        expression = "${1 == 0}"
        context = {}
        assert parse_mako_expression(expression, context) is False

    def test_parse_mako_expression_with_context_false(self):
        expression = "${a != 1}"
        context = {"a": 1}
        assert parse_mako_expression(expression, context) is False

    def test_parse_mako_expression_with_context_complicated_true(self):
        expression = "${not (a == 1 and b == 2 and c == 3)}"
        context = {"a": 1, "b": 3, "c": 3}
        assert parse_mako_expression(expression, context) is True

    def test_parse_mako_expression_with_context_complicated_false(self):
        expression = "${not (a+b == 3 and c == 3)}"
        context = {"a": 1, "b": 2, "c": 3}
        assert parse_mako_expression(expression, context) is False

    def test_parse_mako_expression_with_not_bool_result(self):
        expression = "${1}"
        context = {}
        with pytest.raises(ValueError):
            parse_mako_expression(expression, context)
