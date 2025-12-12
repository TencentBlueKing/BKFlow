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

    dependencies = [
        ("task", "0014_taskflowrelation"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="tasktreeinfo",
            options={"ordering": ["-id"], "verbose_name": "任务流程树信息", "verbose_name_plural": "任务流程树信息"},
        ),
        migrations.CreateModel(
            name="TaskLabelRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_id", models.IntegerField(db_index=True, verbose_name="任务ID")),
                ("label_id", models.IntegerField(db_index=True, verbose_name="标签ID")),
            ],
            options={
                "verbose_name": "任务标签关系 TaskLabelRelation",
                "verbose_name_plural": "任务标签关系 TaskLabelRelation",
                "unique_together": {("task_id", "label_id")},
            },
        ),
    ]
