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


class A2FlowConvertError(Exception):
    """a2flow 转换过程中的结构化错误基类"""

    def __init__(self, error_type, message, node_id=None, field=None, value=None, hint=None):
        self.error_type = error_type
        self.message = message
        self.node_id = node_id
        self.field = field
        self.value = value
        self.hint = hint
        super().__init__(message)

    def to_dict(self):
        result = {"type": self.error_type, "message": self.message}
        if self.node_id is not None:
            result["node_id"] = self.node_id
        if self.field is not None:
            result["field"] = self.field
        if self.value is not None:
            result["value"] = self.value
        if self.hint is not None:
            result["hint"] = self.hint
        return result


class A2FlowValidationError(Exception):
    """包含多个结构化错误的校验异常"""

    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        messages = "; ".join(e.message if isinstance(e, A2FlowConvertError) else str(e) for e in self.errors)
        super().__init__(messages)

    def to_response(self):
        return {
            "result": False,
            "errors": [e.to_dict() if isinstance(e, A2FlowConvertError) else {"message": str(e)} for e in self.errors],
        }


class ErrorTypes:
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    DUPLICATE_NODE_ID = "DUPLICATE_NODE_ID"
    CONDITIONS_MISMATCH = "CONDITIONS_MISMATCH"
    INVALID_DEFAULT_NEXT = "INVALID_DEFAULT_NEXT"
    UNKNOWN_PLUGIN_CODE = "UNKNOWN_PLUGIN_CODE"
    AMBIGUOUS_PLUGIN_CODE = "AMBIGUOUS_PLUGIN_CODE"
    CONVERGE_INFER_FAILED = "CONVERGE_INFER_FAILED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    RESERVED_ID_CONFLICT = "RESERVED_ID_CONFLICT"
