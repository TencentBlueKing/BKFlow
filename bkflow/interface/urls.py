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
from django.conf.urls import url
from django.urls import include

from .itsm.itsm import itsm_approve
from .views import (
    callback,
    get_msg_types,
    home,
    is_admin_or_current_space_superuser,
    is_admin_or_space_superuser,
    user_exit,
)

urlpatterns = [
    url(r"^$", home),
    url(r"^logout/$", user_exit),
    url(r"^is_admin_user/$", is_admin_or_space_superuser),
    url(r"^is_current_space_admin/$", is_admin_or_current_space_superuser),
    url(r"^callback/(?P<token>.+)/$", callback),
    url(r"^get_msg_types/$", get_msg_types),
    url(r"^itsm_approve/$", itsm_approve),
    url(r"", include("bkflow.interface.task.urls")),
]
