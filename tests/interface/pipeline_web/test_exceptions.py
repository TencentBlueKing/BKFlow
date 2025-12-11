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

from django.test import TestCase
from pipeline.exceptions import PipelineException

from bkflow.pipeline_web.exceptions import ParserException, ParserWebTreeException


class TestExceptions(TestCase):
    def test_exceptions(self):
        """测试异常类"""
        # Inheritance
        self.assertTrue(issubclass(ParserException, PipelineException))
        self.assertTrue(issubclass(ParserWebTreeException, ParserException))
        self.assertTrue(issubclass(ParserWebTreeException, PipelineException))

        # Instantiation
        exception = ParserException("test message")
        self.assertEqual(str(exception), "test message")
        self.assertIsInstance(exception, PipelineException)

        exception = ParserWebTreeException("test message")
        self.assertEqual(str(exception), "test message")
        self.assertIsInstance(exception, ParserException)

        # Raise
        with self.assertRaises(ParserException):
            raise ParserException("test")
        with self.assertRaises(ParserWebTreeException):
            raise ParserWebTreeException("test")
