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
from django.conf.urls import url

from bkflow.api_plugin_demo import views

urlpatterns = [
    url(r"^category/$", views.category_api, name="category_api"),
    url(r"^list_meta/$", views.list_meta_api, name="list_meta_api"),
    url(r"^detail_meta/$", views.detail_meta_api, name="detail_meta_api"),
    url(r"^execute/get_user_info/$", views.execute_get_user_info, name="execute_get_user_info"),
    url(r"^execute/create_task/$", views.execute_create_task, name="execute_create_task"),
    url(r"^execute/process_data/$", views.execute_process_data, name="execute_process_data"),
]
