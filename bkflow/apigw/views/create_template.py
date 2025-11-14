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
import copy
import json
import logging

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.template import CreateTemplateSerializer
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.space.utils import build_default_pipeline_tree_with_space_id
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.utils import err_code
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
def create_template(request, space_id):
    """
    创建模板
    data = {}
    """

    data = json.loads(request.body)

    ser = CreateTemplateSerializer(data=data, context={"space_id": int(space_id), "request": request})
    ser.is_valid(raise_exception=True)

    validate_data = dict(ser.data)

    source_template_id = validate_data.pop("source_template_id", None)
    pipeline_tree = validate_data.pop("pipeline_tree", None)
    if source_template_id:
        # 在序列化器中已经判断了存在，所以不需要处理异常
        source_template = Template.objects.get(id=source_template_id)
        pipeline_tree = copy.deepcopy(source_template.pipeline_tree)
        replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)
    elif pipeline_tree:
        replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)
    else:
        pipeline_tree = build_default_pipeline_tree_with_space_id(space_id)

    # 涉及到两张表的创建，需要那个开启事物，确保两张表全部都创建成功
    with transaction.atomic():
        username = validate_data.pop("creator", "") or request.user.username
        snapshot = TemplateSnapshot.create_snapshot(pipeline_tree)
        template = Template.objects.create(
            **validate_data, snapshot_id=snapshot.id, space_id=space_id, updated_by=username, creator=username
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
