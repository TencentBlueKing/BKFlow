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
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.a2flow import CreateTemplateWithA2FlowSerializer
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
)
from bkflow.pipeline_web.drawing_new.drawing import draw_pipeline
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils import err_code
from bkflow.utils.a2flow import A2FlowConverter
from bkflow.utils.canvas import OperateType
from bkflow.utils.pipeline import replace_pipeline_tree_node_ids

logger = logging.getLogger("root")


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
    normalized_version = "2.0" if a2flow_version in (None, "", "2", "2.0", 2, 2.0) else str(a2flow_version)
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
        name = a2flow_data.get("name", "")
        desc = a2flow_data.get("desc", "")
        auto_release = validated_data.pop("auto_release", False)

        try:
            from bkflow.pipeline_converter.converters.a2flow_v2 import A2FlowV2Converter

            converter = A2FlowV2Converter(
                a2flow_data,
                space_id=int(space_id),
                username=request.user.username,
                scope_type=validated_data.get("scope_type"),
                scope_value=validated_data.get("scope_value"),
            )
            pipeline_tree = converter.convert()
        except ValidationError as e:
            logger.exception("create_template_with_a2flow v2: pydantic validation failed")
            return {
                "result": False,
                "errors": [{"type": "MISSING_REQUIRED_FIELD", "message": str(e)}],
                "code": err_code.VALIDATION_ERROR.code,
            }
        except A2FlowValidationError as e:
            logger.exception("create_template_with_a2flow v2: validation failed")
            response = e.to_response()
            response["code"] = err_code.VALIDATION_ERROR.code
            return response
        except A2FlowConvertError as e:
            logger.exception("create_template_with_a2flow v2: convert error")
            return {"result": False, "errors": [e.to_dict()], "code": err_code.VALIDATION_ERROR.code}
        except Exception as e:
            logger.exception("create_template_with_a2flow v2: unexpected error - {}".format(str(e)))
            return {
                "result": False,
                "data": {},
                "message": "流程转换失败: {}".format(str(e)),
                "code": err_code.VALIDATION_ERROR.code,
            }
    elif isinstance(a2flow_raw, dict):
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
    else:
        ser = CreateTemplateWithA2FlowSerializer(data=data)
        ser.is_valid(raise_exception=True)

        validated_data = dict(ser.validated_data)
        a2flow = validated_data.pop("a2flow")
        auto_release = validated_data.pop("auto_release", False)
        name = validated_data.pop("name")
        desc = validated_data.pop("desc", "")

        try:
            converter = A2FlowConverter(a2flow)
            pipeline_tree = converter.convert()
        except (KeyError, ValueError) as e:
            logger.exception("create_template_with_a2flow: conversion failed - {}".format(str(e)))
            return {
                "result": False,
                "data": {},
                "message": "流程转换失败: {}".format(str(e)),
                "code": err_code.VALIDATION_ERROR.code,
            }

    try:
        draw_pipeline(pipeline_tree)
    except Exception as e:
        logger.exception("create_template_with_a2flow: draw_pipeline failed - {}".format(str(e)))
        return {
            "result": False,
            "data": {},
            "message": "流程自动排版失败: {}".format(str(e)),
            "code": err_code.ERROR.code,
        }

    replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)

    with transaction.atomic():
        username = validated_data.pop("creator", "") or request.user.username
        template_data = {
            "name": name,
            "desc": desc,
            "space_id": space_id,
            "creator": username,
            "updated_by": username,
        }

        scope_type = validated_data.pop("scope_type", None)
        scope_value = validated_data.pop("scope_value", None)
        if scope_type:
            template_data["scope_type"] = scope_type
            template_data["scope_value"] = scope_value

        if SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true":
            if auto_release:
                snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username, "1.0.0")
            else:
                snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, username)
        else:
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, username, "1.0.0")

        template = Template.objects.create(**template_data, snapshot_id=snapshot.id)
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
