"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file
except in compliance with the License. You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import pytest

from bkflow.harness.constants import HarnessRunStatus
from bkflow.harness.models import HarnessRun
from bkflow.space.models import Space


@pytest.fixture
def space(db):
    return Space.objects.create(name="harness-p0-space", app_code="bkflow_harness", platform_url="http://example.com")


@pytest.fixture
def harness_run(space):
    return HarnessRun.objects.create(
        platform_key="bkaidev",
        platform_app="bkflow_harness",
        actor="alice",
        space_id=space.id,
        scope_type=None,
        scope_value=None,
        target_environment="stage",
        status=HarnessRunStatus.INTENT_CAPTURED.value,
        policy_version="p0-v1",
        mcp_contract_version="1.0.0",
    )
