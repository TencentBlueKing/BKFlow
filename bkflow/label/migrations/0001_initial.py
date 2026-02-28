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
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TemplateLabelRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("template_id", models.IntegerField(db_index=True, verbose_name="模版ID")),
                ("label_id", models.IntegerField(db_index=True, verbose_name="标签ID")),
            ],
            options={
                "verbose_name": "模版标签关系 TemplateLabelRelation",
                "verbose_name_plural": "模版标签关系 TemplateLabelRelation",
                "unique_together": {("template_id", "label_id")},
            },
        ),
        migrations.CreateModel(
            name="Label",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, verbose_name="标签ID")),
                ("name", models.CharField(db_index=True, help_text="标签名称", max_length=255, verbose_name="标签名称")),
                ("creator", models.CharField(help_text="标签创建人", max_length=255, verbose_name="创建者")),
                ("updated_by", models.CharField(help_text="标签更新人", max_length=255, verbose_name="更新者")),
                (
                    "space_id",
                    models.IntegerField(default=-1, help_text="标签对应的空间id（默认标签时space_id=-1）", verbose_name="空间ID"),
                ),
                ("is_default", models.BooleanField(default=False, help_text="是否是默认标签", verbose_name="默认标签")),
                (
                    "color",
                    models.CharField(default="#dcffe2", help_text="标签颜色值（如#ffffff）", max_length=7, verbose_name="标签颜色"),
                ),
                (
                    "description",
                    models.CharField(blank=True, help_text="标签描述", max_length=255, null=True, verbose_name="标签描述"),
                ),
                (
                    "label_scope",
                    models.JSONField(
                        default="template", help_text="标签范围（支持多选，如['task', 'common']）", verbose_name="标签范围"
                    ),
                ),
                (
                    "parent_id",
                    models.IntegerField(
                        blank=True, default=None, help_text="父标签ID（根标签填null或留空）", null=True, verbose_name="父标签ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "用户标签 Label",
                "verbose_name_plural": "用户标签 Label",
                "ordering": ["space_id", "parent_id", "name"],
                "unique_together": {("space_id", "parent_id", "name")},
            },
        ),
    ]
