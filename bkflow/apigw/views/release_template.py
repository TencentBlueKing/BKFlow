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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.constants import TemplateOperationSource, TemplateOperationType
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.template.serializers.template import TemplateReleaseSerializer
from bkflow.utils import err_code
from bkflow.utils.version import bump_custom

logger = logging.getLogger("root")


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def release_template(request, space_id, template_id):
    data = json.loads(request.body)
    try:
        instance = Template.objects.get(id=template_id, space_id=space_id)
    except Template.DoesNotExist:
        return JsonResponse({"result": False, "message": "Template not found"})

    if SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) != "true":
        return JsonResponse({"result": False, "message": "当前空间未开启版本管理，无法发布模板", "code": err_code.VALIDATION_ERROR.code})

    ser = TemplateReleaseSerializer(data=data)
    ser.is_valid(raise_exception=True)

    new_version = ser.validated_data["version"]
    if TemplateSnapshot.objects.filter(template_id=instance.id, version=new_version).exists():
        return JsonResponse({"result": False, "message": "版本已存在", "code": err_code.VALIDATION_ERROR.code})

    try:
        bump_custom(new_version, instance.version)
    except ValueError as e:
        logger.error(str(e))
        return JsonResponse({"result": False, "message": f"版本号不符合规范: {str(e)}", "code": err_code.VALIDATION_ERROR.code})

    with transaction.atomic():
        data = {"username": request.user.username, **ser.validated_data}
        snapshot = instance.release_template(data)
        instance.snapshot_id = snapshot.id
        instance.save()

    TemplateOperationRecord.objects.create(
        operate_source=TemplateOperationSource.app.name,
        operate_type=TemplateOperationType.release.name,
        instance_id=instance.id,
        operator=request.user.username,
        extra_info={"version": new_version},
    )

    return JsonResponse({"result": True, "data": instance.to_json(), "code": err_code.SUCCESS.code})
