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
from bkflow.decision_table.models import DecisionTable
from bkflow.template.models import Template, TemplateReference, Trigger
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def delete_template(request, space_id, template_id):
    failed_data = {}
    decision_templates = DecisionTable.objects.filter(space_id=space_id, template_id=template_id, is_deleted=False)
    template_references = TemplateReference.objects.filter(subprocess_template_id=template_id)

    if decision_templates.exists():
        failed_data["decision_templates"] = list(decision_templates.values_list("id", flat=True))
    if template_references.exists():
        failed_data["parent_templates"] = list(template_references.values_list("root_template_id", flat=True))
    # 如果存在任何引用，返回错误信息
    if failed_data:
        return {"result": False, "data": failed_data, "code": err_code.VALIDATION_ERROR.code, "message": "模板被引用，无法删除"}

    # 如果没有引用，执行删除操作
    Template.objects.filter(space_id=space_id, id=template_id).update(is_deleted=True)
    trigger_ids = Trigger.objects.filter(template_id=template_id).values_list("id", flat=True)
    Trigger.objects.batch_delete_by_ids(space_id=space_id, trigger_ids=list(trigger_ids))
    return {"result": True, "data": {}, "code": err_code.SUCCESS.code}
