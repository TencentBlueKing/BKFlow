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
from django.conf import settings
from django.conf.urls import url

from module_settings import BKFLOWModuleType

urlpatterns = []

if settings.BKFLOW_MODULE.type == BKFLOWModuleType.interface:
    from bkflow.apigw.views.apply_token import apply_token
    from bkflow.apigw.views.apply_webhook_configs import apply_webhook_configs
    from bkflow.apigw.views.create_credential import create_credential
    from bkflow.apigw.views.create_mock_task import create_mock_task
    from bkflow.apigw.views.create_space import create_space
    from bkflow.apigw.views.create_task import create_task
    from bkflow.apigw.views.create_task_without_template import (
        create_task_without_template,
    )
    from bkflow.apigw.views.create_template import create_template
    from bkflow.apigw.views.delete_task import delete_task
    from bkflow.apigw.views.delete_template import delete_template
    from bkflow.apigw.views.get_space_configs import get_space_configs
    from bkflow.apigw.views.get_task_detail import get_task_detail
    from bkflow.apigw.views.get_task_list import get_task_list
    from bkflow.apigw.views.get_task_node_detail import get_task_node_detail
    from bkflow.apigw.views.get_task_states import get_task_states
    from bkflow.apigw.views.get_tasks_states import get_tasks_states
    from bkflow.apigw.views.get_template_detail import get_template_detail
    from bkflow.apigw.views.get_template_list import get_template_list
    from bkflow.apigw.views.get_template_mock_data import get_template_mock_data
    from bkflow.apigw.views.grant_apigw_permissions_to_app import (
        grant_apigw_permissions_to_app,
    )
    from bkflow.apigw.views.operate_task import operate_task
    from bkflow.apigw.views.operate_task_node import operate_task_node
    from bkflow.apigw.views.renew_space_config import renew_space_config
    from bkflow.apigw.views.revoke_token import revoke_token
    from bkflow.apigw.views.update_template import update_template
    from bkflow.apigw.views.validate_pipeline_tree import validate_pipeline_tree

    urlpatterns += [
        url(r"^create_space/$", create_space),
        url(r"^grant_apigw_permissions_to_app/$", grant_apigw_permissions_to_app),
        url(r"^space/(?P<space_id>\d+)/apply_token/$", apply_token),
        url(r"^space/(?P<space_id>\d+)/revoke_token/$", revoke_token),
        url(r"^space/(?P<space_id>\d+)/create_template/$", create_template),
        url(r"^space/(?P<space_id>\d+)/get_template_list/$", get_template_list),
        url(r"^space/(?P<space_id>\d+)/template/(?P<template_id>\d+)/get_template_detail/$", get_template_detail),
        url(r"^space/(?P<space_id>\d+)/template/(?P<template_id>\d+)/get_template_mock_data/$", get_template_mock_data),
        url(r"^space/(?P<space_id>\d+)/renew_space_config/$", renew_space_config),
        url(r"^space/(?P<space_id>\d+)/get_space_configs/$", get_space_configs),
        url(r"^space/(?P<space_id>\d+)/update_template/(?P<template_id>\d+)/$", update_template),
        url(r"^space/(?P<space_id>\d+)/delete_template/(?P<template_id>\d+)/$", delete_template),
        url(r"^space/(?P<space_id>\d+)/create_task/$", create_task),
        url(r"^space/(?P<space_id>\d+)/create_mock_task/$", create_mock_task),
        url(r"^space/(?P<space_id>\d+)/create_task_without_template/$", create_task_without_template),
        url(r"^space/(?P<space_id>\d+)/validate_pipeline_tree/$", validate_pipeline_tree),
        url(r"^space/(?P<space_id>\d+)/create_credential/$", create_credential),
        url(r"^space/(?P<space_id>\d+)/get_task_list/$", get_task_list),
        url(r"^space/(?P<space_id>\d+)/task/(?P<task_id>\d+)/get_task_detail/$", get_task_detail),
        url(r"^space/(?P<space_id>\d+)/task/(?P<task_id>\d+)/get_task_states/$", get_task_states),
        url(r"^space/(?P<space_id>\d+)/get_tasks_states/$", get_tasks_states),
        url(
            r"^space/(?P<space_id>\d+)/task/(?P<task_id>\d+)/node/(?P<node_id>\w+)/get_task_node_detail/$",
            get_task_node_detail,
        ),
        url(
            r"^space/(?P<space_id>\d+)/task/(?P<task_id>\d+)/node/(?P<node_id>\w+)/operate_node/(?P<operation>\w+)/$",
            operate_task_node,
        ),
        url(r"^space/(?P<space_id>\d+)/task/(?P<task_id>\d+)/operate_task/(?P<operation>\w+)/$", operate_task),
        url(r"^space/(?P<space_id>\d+)/apply_webhook_configs/$", apply_webhook_configs),
        url(r"^space/(?P<space_id>\d+)/delete_task/$", delete_task),
    ]
