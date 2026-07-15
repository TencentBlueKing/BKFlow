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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.template import BatchDeleteTemplateSerializer
from bkflow.decision_table.models import DecisionTable
from bkflow.label.models import TemplateLabelRelation
from bkflow.template.models import Template, TemplateReference, Trigger
from bkflow.utils import err_code
from bkflow.utils.webhook import clear_scope_webhooks


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def batch_delete_template(request, space_id):
    data = json.loads(request.body)
    ser = BatchDeleteTemplateSerializer(data=data)
    ser.is_valid(raise_exception=True)

    template_ids = ser.validated_data["template_ids"]
    failed_data = {}
    decision_templates = list(
        DecisionTable.objects.filter(template_id__in=template_ids, is_deleted=False).values("id", "name", "template_id")
    )
    if decision_templates:
        decision_template_map = {}
        for dec in decision_templates:
            if dec["template_id"] not in decision_template_map:
                decision_template_map[dec["template_id"]] = []

            decision_template_map[dec["template_id"]].append({"id": dec["id"], "name": dec["name"]})
        if decision_template_map:
            failed_data["decision_info"] = decision_template_map

    template_references_obj = TemplateReference.objects.filter(subprocess_template_id__in=template_ids)
    root_template_ids = list(template_references_obj.values_list("root_template_id", flat=True))
    template_references = template_references_obj.values("subprocess_template_id", "root_template_id")

    if template_references:
        sub_root_map = {}
        all_needed_template_ids = set(map(str, template_ids)) | set(root_template_ids)
        templates = Template.objects.filter(id__in=list(all_needed_template_ids), is_deleted=False)
        templates_map = {str(t.id): t.name for t in templates}

        for ref in template_references:
            template_key = ref["subprocess_template_id"]
            root_id = ref["root_template_id"]
            # 如果父流程也在删除列表中或父流程已经被删除了，则跳过
            if (int(root_id) in template_ids) or (root_id not in templates_map):
                continue
            if template_key not in sub_root_map:
                sub_root_map[template_key] = []

            sub_root_map[template_key].append(
                {"root_template_id": root_id, "root_template_name": templates_map.get(str(root_id))}
            )
        if sub_root_map:
            failed_data["root_template_info"] = dict(sub_root_map)

    if failed_data:
        return {"result": False, "data": failed_data, "code": err_code.VALIDATION_ERROR.code, "message": "模板被引用，无法删除"}

    with transaction.atomic():
        Template.objects.filter(space_id=space_id, id__in=template_ids, is_deleted=False).update(is_deleted=True)
        clear_result = clear_scope_webhooks([str(tid) for tid in template_ids])
        if not clear_result["result"]:
            message = clear_result["message"]
            raise Exception(message)
        trigger_ids = Trigger.objects.filter(template_id__in=template_ids).values_list("id", flat=True)
        Trigger.objects.batch_delete_by_ids(space_id=space_id, trigger_ids=list(trigger_ids))
        TemplateLabelRelation.objects.filter(template_id__in=template_ids).delete()

    return {"result": True, "data": {}, "code": err_code.SUCCESS.code}
