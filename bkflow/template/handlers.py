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

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from pipeline.core.constants import PE

from bkflow.template.models import Template, TemplateReference


@receiver(post_save, sender=Template)
def pipeline_template_post_save_handler(sender, instance, created, **kwargs):
    template = instance

    if template.is_deleted:
        TemplateReference.objects.filter(root_template_id=template.id).delete()
        return

    with transaction.atomic():
        TemplateReference.objects.filter(root_template_id=template.id).delete()
        acts = list(template.pipeline_tree[PE.activities].values())
        subprocess_nodes = [act for act in acts if act["type"] == PE.SubProcess]
        rs = []
        for sp in subprocess_nodes:
            subprocess_template_id = int(sp["template_id"])
            version = sp.get("version") or Template.objects.get(id=subprocess_template_id).version
            always_use_latest = sp.get("always_use_latest", False)

            rs.append(
                TemplateReference(
                    root_template_id=template.id,
                    subprocess_template_id=subprocess_template_id,
                    subprocess_node_id=sp["id"],
                    version=version,
                    always_use_latest=always_use_latest,
                )
            )
        if rs:
            TemplateReference.objects.bulk_create(rs)
