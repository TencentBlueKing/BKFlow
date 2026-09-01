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

import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.a2flow import CreateTemplateWithA2FlowSerializer
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.pipeline_converter.constants import normalize_a2flow_version
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
)
from bkflow.template.services.a2flow_template import create_template_from_a2flow
from bkflow.utils import err_code

logger = logging.getLogger("root")


def _bind_app_code(request):
    return getattr(getattr(request, "app", None), "bk_app_code", "") or ""


def _create_error_response(exc, *, structured=False):
    if isinstance(exc, A2FlowValidationError):
        response = exc.to_response()
        response["code"] = err_code.VALIDATION_ERROR.code
        return response
    if isinstance(exc, A2FlowConvertError):
        return {"result": False, "errors": [exc.to_dict()], "code": err_code.VALIDATION_ERROR.code}
    if isinstance(exc, ValidationError):
        return {
            "result": False,
            "errors": [{"type": "MISSING_REQUIRED_FIELD", "message": str(exc)}],
            "code": err_code.VALIDATION_ERROR.code,
        }
    if isinstance(exc, RuntimeError) and str(exc).startswith("流程自动排版失败"):
        return {"result": False, "data": {}, "message": str(exc), "code": err_code.ERROR.code}
    if structured:
        return {
            "result": False,
            "data": {},
            "message": "流程转换失败: {}".format(str(exc)),
            "code": err_code.VALIDATION_ERROR.code,
        }
    return {
        "result": False,
        "data": {},
        "message": "流程转换失败: {}".format(str(exc)),
        "code": err_code.VALIDATION_ERROR.code,
    }


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
@record_operation(
    RecordType.template.name,
    TemplateOperationType.create.name,
    TemplateOperationSource.api.name,
    extra_info={"tag": "apigw"},
)
def create_template_with_a2flow(request, space_id):
    """导入简化流程 JSON 并创建模板，支持 v1 / v2 协议自动路由"""
    data = json.loads(request.body)

    a2flow_raw = data.get("a2flow")
    a2flow_version = a2flow_raw.get("version", "2.0") if isinstance(a2flow_raw, dict) else None
    normalized_version = normalize_a2flow_version(a2flow_version)
    is_v2 = isinstance(a2flow_raw, dict) and normalized_version == "2.0"

    if is_v2:
        from bkflow.apigw.serializers.a2flow import (
            CreateTemplateWithA2FlowV2Serializer,
            build_structured_serializer_errors,
        )

        ser = CreateTemplateWithA2FlowV2Serializer(data=data)
        if not ser.is_valid():
            return {
                "result": False,
                "errors": build_structured_serializer_errors(ser.errors, prefix="a2flow"),
                "code": err_code.VALIDATION_ERROR.code,
            }
        validated_data = dict(ser.validated_data)
        a2flow_data = validated_data.pop("a2flow")
        try:
            template = create_template_from_a2flow(
                space_id=int(space_id),
                username=validated_data.pop("creator", "") or request.user.username,
                a2flow=a2flow_data,
                scope_type=validated_data.get("scope_type"),
                scope_value=validated_data.get("scope_value"),
                bind_app_code=_bind_app_code(request),
                auto_release=validated_data.pop("auto_release", False),
            )
        except Exception as exc:
            logger.exception("create_template_with_a2flow v2 failed")
            return _create_error_response(exc, structured=True)
        return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}

    if isinstance(a2flow_raw, dict):
        return {
            "result": False,
            "errors": [
                {
                    "type": "UNSUPPORTED_VERSION",
                    "field": "version",
                    "value": normalized_version,
                    "message": "不支持的 a2flow 版本: '{}'".format(normalized_version),
                    "hint": "当前支持版本: 1.0(数组格式), 2.0(对象格式)",
                }
            ],
            "code": err_code.VALIDATION_ERROR.code,
        }

    ser = CreateTemplateWithA2FlowSerializer(data=data)
    ser.is_valid(raise_exception=True)
    validated_data = dict(ser.validated_data)
    a2flow = validated_data.pop("a2flow")
    try:
        template = create_template_from_a2flow(
            space_id=int(space_id),
            username=validated_data.pop("creator", "") or request.user.username,
            a2flow=a2flow,
            scope_type=validated_data.get("scope_type"),
            scope_value=validated_data.get("scope_value"),
            bind_app_code=_bind_app_code(request),
            auto_release=validated_data.pop("auto_release", False),
            name=validated_data.pop("name"),
            desc=validated_data.pop("desc", ""),
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        logger.exception("create_template_with_a2flow: conversion failed - {}".format(str(exc)))
        return _create_error_response(exc)
    except Exception as exc:
        logger.exception("create_template_with_a2flow: unexpected error - {}".format(str(exc)))
        return _create_error_response(exc)

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
