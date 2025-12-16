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
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.exceptions import UpdateTemplateException
from bkflow.apigw.serializers.template import UpdateTemplateSerializer
from bkflow.constants import TemplateOperationSource, TemplateOperationType
from bkflow.exceptions import ValidationError
from bkflow.space.configs import FlowVersioning
from bkflow.space.models import SpaceConfig
from bkflow.template.models import Template, TemplateOperationRecord, TemplateSnapshot
from bkflow.utils import err_code
from bkflow.utils.canvas import OperateType
from bkflow.utils.pipeline import replace_pipeline_tree_node_ids
from bkflow.utils.version import bump_custom


@login_exempt
@csrf_exempt
@require_POST
@check_jwt_and_space
@return_json_response
def update_template(request, space_id, template_id):
    data = json.loads(request.body)

    ser = UpdateTemplateSerializer(data=data, context={"request": request})

    try:
        ser.is_valid(raise_exception=True)
    except Exception as e:
        raise ValidationError(e)

    validated_data_dict = dict(ser.data)

    auto_release = validated_data_dict.pop("auto_release", False)
    version = validated_data_dict.pop("version", None)

    pipeline_tree = validated_data_dict.pop("pipeline_tree", None)
    if pipeline_tree:
        replace_pipeline_tree_node_ids(pipeline_tree, OperateType.CREATE_TEMPLATE.value)

    validated_data_dict["updated_by"] = validated_data_dict.pop("operator", None) or request.user.username
    with transaction.atomic():
        try:
            template = Template.objects.get(id=template_id, space_id=space_id, is_deleted=False)
        except Template.DoesNotExist:
            raise UpdateTemplateException(_(f"模板不存在，template_id:{template_id}"))

        # 添加更新记录
        TemplateOperationRecord.objects.create(
            operate_source=TemplateOperationSource.api.name,
            operate_type=TemplateOperationType.update.name,
            instance_id=template.id,
            operator=request.user.username,
        )

        if pipeline_tree:
            if SpaceConfig.get_config(space_id=space_id, config_name=FlowVersioning.name) == "true":
                try:
                    TemplateSnapshot.objects.get(template_id=template_id, draft=True)
                    template_version = None
                except TemplateSnapshot.DoesNotExist:
                    template_version = template.version
                # 更新草稿数据
                template.update_draft_snapshot(pipeline_tree, request.user.username, template_version)

                if auto_release:
                    if version:
                        release_version = version
                    elif template.snapshot_version:
                        release_version = bump_custom(template.snapshot_version)
                    else:
                        release_version = "1.0.0"

                    if TemplateSnapshot.objects.filter(template_id=template.id, version=release_version).exists():
                        raise UpdateTemplateException(_(f"版本号已存在: {version}"))
                    try:
                        bump_custom(release_version, template.snapshot_version)
                    except Exception as e:
                        raise UpdateTemplateException(_(f"版本号不符合规范: {str(e)}"))

                    snapshot = template.release_template(
                        {"version": release_version, "username": request.user.username}
                    )
                    template.snapshot_id = snapshot.id

                    # 添加发布记录
                    TemplateOperationRecord.objects.create(
                        operate_source=TemplateOperationSource.api.name,
                        operate_type=TemplateOperationType.release.name,
                        instance_id=template.id,
                        operator=request.user.username,
                        extra_info={"version": release_version},
                    )
            else:
                if not template.snapshot_version:
                    current_version = "1.0.0"
                else:
                    current_version = bump_custom(template.snapshot_version)
                snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, request.user.username, current_version)
                validated_data_dict["snapshot_id"] = snapshot.id
                snapshot.template_id = template.id
                snapshot.save(update_fields=["template_id"])

        for key, value in validated_data_dict.items():
            setattr(template, key, value)
        try:
            template.save()
        except Exception as e:
            raise UpdateTemplateException(_(f"保存模板失败，错误: {str(e)}"))

    template = Template.objects.get(id=template_id)

    return {"result": True, "data": template.to_json(), "code": err_code.SUCCESS.code}
