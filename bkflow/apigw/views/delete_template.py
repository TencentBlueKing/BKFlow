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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.template.models import Template
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
@record_operation(
    RecordType.template.name,
    TemplateOperationType.delete.name,
    TemplateOperationSource.api.name,
    extra_info={"tag": "apigw"},
)
def delete_template(request, space_id, template_id):
    count, _ = Template.objects.filter(space_id=space_id, id=template_id).delete()
    return {"result": True, "data": {"count": count}, "code": err_code.SUCCESS.code}
