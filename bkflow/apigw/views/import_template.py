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
import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.template import ImportTemplateSerializer
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.pipeline_converter.constants import DataTypes
from bkflow.pipeline_converter.hub import CONVERTER_HUB
from bkflow.pipeline_web.drawing_new.drawing import draw_pipeline
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils import err_code

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
def import_template(request, space_id):
    data = json.loads(request.body)

    ser = ImportTemplateSerializer(data=data, context={"request": request})
    ser.is_valid(raise_exception=True)

    validate_data = dict(ser.validated_data)
    pipeline_data = validate_data.pop("pipeline_data")

    json_pipeline_cvt = CONVERTER_HUB.get_converter_cls(
        DataTypes.JSON.value, DataTypes.DATA_MODEL.value, "PipelineConverter"
    )
    dm_pipeline = json_pipeline_cvt(pipeline_data).convert()
    data_model_pipeline_cvt = CONVERTER_HUB.get_converter_cls(
        DataTypes.DATA_MODEL.value, DataTypes.WEB_PIPELINE.value, "PipelineConverter"
    )
    web_pipeline_tree = data_model_pipeline_cvt(dm_pipeline).convert()
    draw_pipeline(web_pipeline_tree)

    # 涉及到两张表的创建，需要开启事务，确保两张表全部都创建成功
    with transaction.atomic():
        username = validate_data.pop("creator") or request.user.username
        snapshot = TemplateSnapshot.create_snapshot(web_pipeline_tree)
        template = Template.objects.create(
            **validate_data, snapshot_id=snapshot.id, space_id=space_id, updated_by=username, creator=username
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
