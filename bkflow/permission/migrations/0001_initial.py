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
# Generated by Django 3.2.15 on 2023-03-23 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Token",
            fields=[
                ("token", models.CharField(max_length=32, primary_key=True, serialize=False, verbose_name="Token值")),
                ("space_id", models.IntegerField(verbose_name="空间ID")),
                ("user", models.CharField(max_length=32, verbose_name="用户名")),
                ("resource_type", models.CharField(max_length=32, verbose_name="资源类型")),
                ("resource_id", models.CharField(max_length=32, verbose_name="资源ID")),
                (
                    "permission_type",
                    models.CharField(
                        choices=[("VIEW", "查看"), ("EDIT", "编辑")],
                        default="VIEW",
                        help_text="权限类型",
                        max_length=32,
                    ),
                ),
                ("expired_time", models.DateTimeField(verbose_name="过期时间")),
            ],
            options={
                "verbose_name": "token 表",
                "verbose_name_plural": "token 表",
                "index_together": {
                    ("space_id", "user", "resource_type", "resource_id", "permission_type", "expired_time")
                },
            },
        ),
    ]
