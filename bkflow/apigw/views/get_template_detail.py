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

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.template import TemplateDetailQuerySerializer
from bkflow.pipeline_web.preview import preview_template_tree
from bkflow.pipeline_web.preview_base import PipelineTemplateWebPreviewer
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateMockData, TemplateMockScheme
from bkflow.utils import err_code
from bkflow.utils.pipeline import replace_subprocess_version


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_template_detail(request, space_id, template_id):
    params_validator = TemplateDetailQuerySerializer(data=request.GET)
    params_validator.is_valid(raise_exception=True)
    params = params_validator.validated_data

    try:
        template = Template.objects.get(space_id=space_id, id=template_id)
    except Template.DoesNotExist:
        return {
            "result": False,
            "message": f'Template with ID "{template_id}" does not exist',
            "code": err_code.VALIDATION_ERROR.code,
        }
    response = {
        "result": True,
        "data": template.to_json(),
        "code": err_code.SUCCESS.code,
    }
    copy_pipeline_tree = copy.deepcopy(template.pipeline_tree)

    if params["with_mock_data"]:
        # 获取当前的 mock scheme
        mock_scheme = TemplateMockScheme.objects.filter(space_id=space_id, template_id=template_id).first()
        appoint_node_ids = mock_scheme.data.get("nodes", [])
        response["data"]["appoint_node_ids"] = appoint_node_ids
        # 获取当前的 mock data
        mock_data = list(
            TemplateMockData.objects.filter(
                template_id=template.id, space_id=template.space_id, node_id__in=appoint_node_ids
            ).values("node_id", "data", "is_default")
        )
        response["data"]["mock_data"] = mock_data

        # 仅当有指定的 mock 节点时，才去简化 pipeline_tree
        if appoint_node_ids:
            pipeline_tree = template.pipeline_tree
            exclude_task_nodes_id = PipelineTemplateWebPreviewer.get_template_exclude_task_nodes_with_appoint_nodes(
                pipeline_tree, appoint_node_ids
            )
            preview_data = preview_template_tree(pipeline_tree, exclude_task_nodes_id)
            copy_pipeline_tree = preview_data["pipeline_tree"]

    flow_version_config = SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true"
    copy_pipeline_tree = replace_subprocess_version(copy_pipeline_tree, flow_version_config)

    response["data"]["pipeline_tree"] = copy_pipeline_tree
    return response
