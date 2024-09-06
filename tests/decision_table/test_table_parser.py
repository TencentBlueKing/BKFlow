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

from bkflow.decision_table.table_parser import DecisionTableParser
from tests.decision_table.tables import (
    expression_table,
    or_and_condition_table,
    simple_table,
)


def test_simple_decision_table_parser():
    parser = DecisionTableParser(title="simple_table", decision_table=simple_table)
    decision_table = parser.parse()
    facts = {"text_area": "a", "int_area": 0, "select_area": "value1"}
    decision_result = decide_single_table(decision_table, facts)
    assert decision_result == [{"output_area": "1"}]

    not_match_facts = {"text_area": "b", "int_area": 0, "select_area": "value1"}
    decision_result = decide_single_table(decision_table, not_match_facts, strict_mode=False)
    assert decision_result == []


def test_or_and_condition_decision_table_parser():
    parser = DecisionTableParser(title="or_and_condition_table", decision_table=or_and_condition_table)
    decision_table = parser.parse()

    fact_1 = {"text_area": "2", "int_area": 0, "select_area": "option1"}
    decision_result = decide_single_table(decision_table, fact_1)
    assert decision_result == [{"output_area": "1"}]

    fact_2 = {"text_area": "1", "int_area": 1, "select_area": "option1"}
    decision_result = decide_single_table(decision_table, fact_2)
    assert decision_result == [{"output_area": "2"}]

    fact_3 = {"text_area": "1234", "int_area": 0, "select_area": "option1"}
    decision_result = decide_single_table(decision_table, fact_3)
    assert decision_result == [{"output_area": "3"}]

    fact_4 = {"text_area": "1", "int_area": 5, "select_area": "option1"}
    decision_result = decide_single_table(decision_table, fact_4)
    assert decision_result == [{"output_area": "4"}]


def test_expression_decision_table_parser():
    parser = DecisionTableParser(title="expression_table", decision_table=expression_table)
    decision_table = parser.parse()
    facts = {"int_area": 2}
    decision_result = decide_single_table(decision_table, facts)
    assert decision_result == [{"output_area": "2"}]
