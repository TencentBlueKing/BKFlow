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
import time

import pytest
from bamboo_engine import api
from bamboo_engine.api import EngineAPIResult
from bamboo_engine.builder import (
    EmptyEndEvent,
    EmptyStartEvent,
    ServiceActivity,
    build_tree,
)
from django.conf import settings
from pipeline.eri.runtime import BambooDjangoRuntime


@pytest.mark.skip
@pytest.mark.django_db(transaction=True)
def test_one_node_task(celery_worker):
    start = EmptyStartEvent()
    act_1 = ServiceActivity(component_code="example_component")
    end = EmptyEndEvent()

    start.extend(act_1).extend(end)

    pipeline = build_tree(start)

    runtime = BambooDjangoRuntime()
    api.run_pipeline(runtime, pipeline=pipeline, queue=settings.BKFLOW_MODULE.code)

    # 等待 1s 后获取流程执行结果
    time.sleep(1)

    result = api.get_pipeline_states(runtime=runtime, root_id=pipeline["id"])
    assert isinstance(result, EngineAPIResult)
    assert next(iter(result.data.values()))["state"] == "FINISHED"
