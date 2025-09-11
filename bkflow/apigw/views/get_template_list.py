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
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.template import TemplateListFilterSerializer
from bkflow.apigw.utils import paginate_list_data
from bkflow.template.models import Template, Trigger
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_template_list(request, space_id):
    params_validator = TemplateListFilterSerializer(data=request.GET)
    params_validator.is_valid(raise_exception=True)

    params_validator_data = dict(params_validator.data)

    order_by = params_validator_data.pop("order_by")

    filter_map = {
        "name": "name__icontains",
        "create_at_end": "create_at__lte",
        "create_at_start": "create_at__gte",
    }

    filter_kwargs = {}

    for key, value in params_validator_data.items():
        if key in filter_map:
            filter_kwargs[filter_map[key]] = value
            continue
        filter_kwargs[key] = value

    template_queryset = Template.objects.filter(space_id=space_id, is_deleted=False, **filter_kwargs).order_by(order_by)

    templates, count = paginate_list_data(request, template_queryset)

    data = []

    has_trigger_template_ids = set(Trigger.objects.all().values_list("template_id", flat=True))
    for template in templates:
        json_data = template.to_json(with_pipeline_tree=False)
        if template.id in has_trigger_template_ids:
            json_data["has_interval_trigger"] = True
        else:
            json_data["has_interval_trigger"] = False
        data.append(json_data)

    response = {
        "result": True,
        "data": data,
        "count": count,
        "code": err_code.SUCCESS.code,
    }
    return response
