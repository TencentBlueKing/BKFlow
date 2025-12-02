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
import logging

from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from pipeline.validators import validate_pipeline_tree
from rest_framework import serializers

from bkflow.space.configs import FlowVersioning
from bkflow.space.models import Space, SpaceConfig
from bkflow.template.models import Template, TemplateSnapshot

logger = logging.getLogger("root")


class TemplateSerializers(serializers.ModelSerializer):
    pipeline_tree = serializers.JSONField(required=True)

    snapshot_id = serializers.IntegerField(help_text=_("快照ID"), required=False, read_only=True)
    notify_config = serializers.JSONField(help_text=_("配置"), required=False)
    create_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")
    update_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S%z")

    def validate_space_id(self, space_id):
        if not Space.objects.filter(space_id=space_id).exists():
            raise serializers.ValidationError(_("创建失败，对应的空间不存在"))

        return space_id

    def validate_pipeline_tree(self, pipeline_tree):
        # 校验树的合法性
        try:
            validate_pipeline_tree(pipeline_tree)
        except Exception as e:
            logger.exception("CreateTemplateSerializer pipeline validate error, err = {}".format(e))
            raise serializers.ValidationError(_("参数校验失败，pipeline校验不通过, err={msg}").format(msg=e))

        return pipeline_tree

    @transaction.atomic()
    def create(self, validated_data):
        pipeline_tree = validated_data.pop("pipeline_tree", None)
        if SpaceConfig.get_config(space_id=validated_data["space_id"], config_name=FlowVersioning.name) == "true":
            snapshot = TemplateSnapshot.create_draft_snapshot(pipeline_tree, validated_data["creator"])
        else:
            snapshot = TemplateSnapshot.create_snapshot(pipeline_tree, validated_data["creator"], "1.0.0")
        validated_data["snapshot_id"] = snapshot.id
        return super().create(validated_data)

    @transaction.atomic()
    def update(self, instance, validated_data):
        # 需要校验哪些字段是不可以更新的
        pipeline_tree = validated_data.pop("pipeline_tree", None)
        instance.update_snapshot(pipeline_tree)
        return super().update(instance, validated_data)

    class Meta:
        model = Template
        fields = "__all__"
