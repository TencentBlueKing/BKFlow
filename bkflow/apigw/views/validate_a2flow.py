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
from bkflow.apigw.serializers.plugin import ValidateA2FlowSerializer
from bkflow.pipeline_converter.exceptions import (
    A2FlowConvertError,
    A2FlowValidationError,
)
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def validate_a2flow(request, space_id):
    """预校验 a2flow v2 流程定义（dry-run，不创建模板）"""
    data = json.loads(request.body)

    ser = ValidateA2FlowSerializer(data=data)
    if not ser.is_valid():
        from bkflow.apigw.serializers.a2flow import build_structured_serializer_errors

        return {
            "result": False,
            "errors": build_structured_serializer_errors(ser.errors, prefix="a2flow"),
            "code": err_code.VALIDATION_ERROR.code,
        }

    validated_data = ser.validated_data
    a2flow_data = validated_data["a2flow"]

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
        return {
            "result": False,
            "errors": [{"type": "MISSING_REQUIRED_FIELD", "message": str(e)}],
            "code": err_code.VALIDATION_ERROR.code,
        }
    except A2FlowValidationError as e:
        response = e.to_response()
        response["code"] = err_code.VALIDATION_ERROR.code
        return response
    except A2FlowConvertError as e:
        return {
            "result": False,
            "errors": [e.to_dict()],
            "code": err_code.VALIDATION_ERROR.code,
        }
    except Exception as e:
        logger.exception("validate_a2flow: unexpected error - %s", str(e))
        return {
            "result": False,
            "message": "流程校验失败: {}".format(str(e)),
            "code": err_code.ERROR.code,
            "data": None,
        }

    activities = pipeline_tree.get("activities", {})
    plugin_codes = list({act["component"]["code"] for act in activities.values()})

    return {
        "result": True,
        "data": {
            "valid": True,
            "version": a2flow_data.get("version", "2.0"),
            "node_count": len(activities),
            "plugin_codes": plugin_codes,
        },
        "code": err_code.SUCCESS.code,
    }
