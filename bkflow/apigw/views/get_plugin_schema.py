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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.plugin import GetPluginSchemaSerializer
from bkflow.plugin.services.plugin_schema_service import PluginSchemaService
from bkflow.utils import err_code

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_plugin_schema(request, space_id):
    """查询单个插件的完整参数 schema"""
    ser = GetPluginSchemaSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)
    params = ser.validated_data

    service = PluginSchemaService(
        space_id=int(space_id),
        username=request.user.username,
        scope_type=params.get("scope_type"),
        scope_id=params.get("scope_id"),
    )

    try:
        result = service.get_plugin_schema(
            code=params.get("plugin_id") or params["code"],
            version=params.get("plugin_version") or params.get("version"),
            plugin_type=params.get("plugin_type"),
        )
    except ValueError as e:
        return {
            "result": False,
            "message": str(e),
            "code": err_code.VALIDATION_ERROR.code,
            "data": None,
        }
    except Exception as e:
        logger.exception("get_plugin_schema: unexpected error - %s", str(e))
        return {
            "result": False,
            "message": "查询插件 schema 失败: {}".format(str(e)),
            "code": err_code.ERROR.code,
            "data": None,
        }

    return {"result": True, "data": result, "code": err_code.SUCCESS.code}
