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
# Generated by Django 3.2.15 on 2023-12-22 09:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("template", "0002_auto_20230518_1306"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="templateoperationrecord",
            options={"ordering": ["-id"], "verbose_name": "模版操作记录", "verbose_name_plural": "模版操作记录"},
        ),
        migrations.CreateModel(
            name="TemplateMockScheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("space_id", models.IntegerField(verbose_name="Space ID")),
                ("template_id", models.BigIntegerField(verbose_name="Template ID")),
                ("data", models.JSONField(verbose_name="Mock Scheme Data")),
                ("operator", models.CharField(blank=True, max_length=32, null=True, verbose_name="operator")),
                ("create_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("update_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "Template Mock Scheme",
                "verbose_name_plural": "Template Mock Scheme",
                "ordering": ["-id"],
                "index_together": {("space_id", "template_id")},
            },
        ),
        migrations.CreateModel(
            name="TemplateMockData",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, verbose_name="Mock Data Name")),
                ("space_id", models.IntegerField(verbose_name="Space ID")),
                ("template_id", models.BigIntegerField(verbose_name="Template ID")),
                ("node_id", models.CharField(max_length=33, verbose_name="Node ID")),
                ("data", models.JSONField(verbose_name="Mock Data")),
                ("is_default", models.BooleanField(default=False, verbose_name="Is Default")),
                ("extra_info", models.JSONField(blank=True, null=True, verbose_name="Extra Info")),
                ("operator", models.CharField(blank=True, max_length=32, null=True, verbose_name="operator")),
                ("create_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("update_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "Template Mock Data",
                "verbose_name_plural": "Template Mock Data",
                "ordering": ["-id"],
                "index_together": {("space_id", "template_id", "node_id")},
            },
        ),
    ]
