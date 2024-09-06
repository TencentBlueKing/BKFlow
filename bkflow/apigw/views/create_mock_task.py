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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.task import CreateMockTaskWithTemplateIdSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.exceptions import ValidationError
from bkflow.template.models import Template


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def create_mock_task(request, space_id):
    data = json.loads(request.body)
    ser = CreateMockTaskWithTemplateIdSerializer(data=data)
    ser.is_valid(raise_exception=True)
    # 序列化器已经检查过是否存在了
    try:
        template = Template.objects.get(id=ser.data["template_id"], space_id=space_id)
    except Template.DoesNotExist:
        raise ValidationError(
            _("模版不存在，space_id={space_id}, template_id={template_id}").format(
                space_id=space_id, template_id=ser.data["template_id"]
            )
        )

    # 接口侧先忽略 mock scheme 配置，默认走全部节点的执行
    # # 获取当前的 mock scheme
    # mock_scheme = TemplateMockScheme.objects.filter(space_id=space_id, template_id=template.id).first()
    # if mock_scheme is None:
    #     return {
    #         "result": False,
    #         "message": f'Mock scheme for template "{template.id}" does not exist',
    #         "code": err_code.VALIDATION_ERROR.code,
    #     }
    #
    # appoint_node_ids = mock_scheme.data.get("nodes", [])
    #
    # pipeline_tree = template.pipeline_tree
    # exclude_task_nodes_id = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes(
    #     pipeline_tree, appoint_node_ids
    # )
    # preview_data = preview_template_tree(pipeline_tree, exclude_task_nodes_id)
    # simplified_pipeline_tree = preview_data["pipeline_tree"]

    create_task_data = dict(ser.data)
    create_task_data.update(
        {
            "template_id": template.id,
            "space_id": space_id,
            "scope_type": template.scope_type,
            "scope_value": template.scope_value,
            "pipeline_tree": template.pipeline_tree,
            "mock_data": ser.validated_data["mock_data"],
            "create_method": "MOCK",
        }
    )
    DEFAULT_NOTIFY_CONFIG = {
        "notify_type": {"fail": [], "success": []},
        "notify_receivers": {"more_receiver": "", "receiver_group": []},
    }
    create_task_data.setdefault("extra_info", {}).update(
        {"notify_config": template.notify_config or DEFAULT_NOTIFY_CONFIG}
    )

    client = TaskComponentClient(space_id=space_id)
    result = client.create_task(create_task_data)
    return result
