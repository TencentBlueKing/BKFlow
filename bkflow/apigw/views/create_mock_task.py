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
from bkflow.constants import TaskTriggerMethod
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.exceptions import ValidationError
from bkflow.template.models import Template, TemplateSnapshot


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
    try:
        template = Template.objects.get(id=ser.data["template_id"], space_id=space_id, is_deleted=False)
    except Template.DoesNotExist:
        raise ValidationError(
            _("模版不存在，space_id={space_id}, template_id={template_id}").format(
                space_id=space_id, template_id=ser.data["template_id"]
            )
        )

    # 优先使用草稿版本的 pipeline_tree，如果没有草稿版本则使用最新发布版本
    try:
        draft_snapshot = TemplateSnapshot.objects.get(template_id=template.id, draft=True, is_deleted=False)
        pipeline_tree = draft_snapshot.data
    except TemplateSnapshot.DoesNotExist:
        # 如果没有草稿版本，使用最新发布版本
        pipeline_tree = template.pipeline_tree

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
            "pipeline_tree": pipeline_tree,
            "mock_data": ser.validated_data["mock_data"],
            "create_method": "MOCK",
            "trigger_method": TaskTriggerMethod.api.name,
        }
    )
    DEFAULT_NOTIFY_CONFIG = {
        "notify_type": {"fail": [], "success": []},
        "notify_receivers": {"more_receiver": "", "receiver_group": []},
    }
    create_task_data.setdefault("extra_info", {}).update(
        {"notify_config": template.notify_config or DEFAULT_NOTIFY_CONFIG}
    )

    # 将credentials放入extra_info的custom_context中，以便通过TaskContext和parent_data.inputs获取
    # custom_context用于统一管理自定义上下文数据
    credentials = ser.data.get("credentials", {})
    if credentials:
        create_task_data.setdefault("extra_info", {}).setdefault("custom_context", {})["credentials"] = credentials

    # 将custom_span_attributes放入extra_info的custom_context中，以便通过TaskContext和parent_data.inputs获取
    # 用于传递到节点Span中
    custom_span_attributes = ser.data.get("custom_span_attributes", {})
    if custom_span_attributes:
        create_task_data.setdefault("extra_info", {}).setdefault("custom_context", {})[
            "custom_span_attributes"
        ] = custom_span_attributes

    client = TaskComponentClient(space_id=space_id)
    result = client.create_task(create_task_data)
    return result
