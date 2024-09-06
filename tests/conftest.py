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
import os

import pytest
from django.conf import settings


@pytest.fixture(scope="session")
def env_insert_fixture(request):
    env_pairs = request.param
    for k, v in env_pairs.items():
        os.environ[k] = v
    yield
    for k in env_pairs.keys():
        os.environ.pop(k)


@pytest.fixture(scope="session")
def original_value_fixture(request):
    return request.param


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": "redis://localhost:6379/0",
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    module_code = settings.BKFLOW_MODULE.code
    return {
        "queues": (f"er_execute_{module_code}", f"er_schedule_{module_code}"),
        "perform_ping_check": False,
        "queue_arguments": {"x-max-priority": 255},
    }
