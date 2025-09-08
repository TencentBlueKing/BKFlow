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

from blueapps.account.decorators import login_exempt
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.exceptions import UpdateTemplateException
from bkflow.apigw.serializers.template import UpdateTemplateSerializer
from bkflow.constants import RecordType, TemplateOperationSource, TemplateOperationType
from bkflow.contrib.operation_record.decorators import record_operation
from bkflow.exceptions import ValidationError
from bkflow.template.models import Template
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@check_jwt_and_space
@return_json_response
@record_operation(
    RecordType.template.name,
    TemplateOperationType.update.name,
    TemplateOperationSource.api.name,
    extra_info={"tag": "apigw"},
)
def update_template(request, space_id, template_id):
    data = json.loads(request.body)

    ser = UpdateTemplateSerializer(data=data, context={"request": request})

    try:
        ser.is_valid(raise_exception=True)
    except Exception as e:
        raise ValidationError(e)

    validated_data_dict = dict(ser.data)

    validated_data_dict["updated_by"] = validated_data_dict.pop("operator", None) or request.user.username
    template = Template.objects.filter(id=template_id, space_id=space_id, is_deleted=False)
    if not template.exists():
        raise UpdateTemplateException(_(f"模板不存在，template_id:{template_id}"))
    success = template.update(**validated_data_dict)
    # 表示更新失败
    if not success:
        raise UpdateTemplateException(_(f"请检查参数，params:{validated_data_dict}"))

    template = Template.objects.get(id=template_id)

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
