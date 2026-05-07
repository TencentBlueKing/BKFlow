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

from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from django.test import TestCase

from bkflow.label.models import Label
from bkflow.space.models import Space
from bkflow.template.models import Template, TemplateSnapshot


class LabelApigwTestBase(TestCase):
    def setUp(self):
        self.space = Space.objects.create(app_code="test", platform_url="http://test.com", name="label_space")

    def build_pipeline_tree(self):
        start = EmptyStartEvent()
        act_1 = ServiceActivity(component_code="example_component")
        end = EmptyEndEvent()
        start.extend(act_1).extend(end)
        return build_tree(start, data={"test": "test"})

    def create_label(self, name, scope, parent_id=None, **kwargs):
        data = {
            "name": name,
            "creator": kwargs.pop("creator", "tester"),
            "updated_by": kwargs.pop("updated_by", "tester"),
            "space_id": self.space.id,
            "label_scope": scope,
            "color": kwargs.pop("color", "#FFFFFF"),
            **kwargs,
        }
        if parent_id is not None:
            data["parent_id"] = parent_id
        return Label.objects.create(**data)

    def create_template(self, name="template"):
        snapshot = TemplateSnapshot.create_snapshot(self.build_pipeline_tree(), "tester", "1.0.0")
        template = Template.objects.create(
            name=name,
            space_id=self.space.id,
            snapshot_id=snapshot.id,
            creator="tester",
            updated_by="tester",
        )
        snapshot.template_id = template.id
        snapshot.save(update_fields=["template_id"])
        return template
