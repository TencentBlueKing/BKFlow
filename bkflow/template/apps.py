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
from django.apps import AppConfig


class TemplateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bkflow.template"

    def ready(self):
        from bkflow.constants import RecordType  # noqa
        from bkflow.contrib.operation_record import OPERATION_RECORDER  # noqa
        from bkflow.template.handlers import pipeline_template_post_save_handler  # noqa
        from bkflow.template.operation_record import TemplateOperationRecorder  # noqa

        OPERATION_RECORDER.register(RecordType.template.name, TemplateOperationRecorder)
