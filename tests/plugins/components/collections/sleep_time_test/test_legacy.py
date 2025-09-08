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
import datetime
import time
import zoneinfo

from django.conf import settings
from django.test import TestCase
from pipeline.component_framework.test import (
    ComponentTestCase,
    ComponentTestMixin,
    ExecuteAssertion,
    ScheduleAssertion,
)

from bkflow.pipeline_plugins.components.collections.sleep_time.legacy import (
    SleepTimerComponent,
)


class SleepTimerComponentTest(TestCase, ComponentTestMixin):
    def component_cls(self):
        return SleepTimerComponent

    def cases(self):
        return [INVALID_SECONDS_TEST_CASE, VALID_DATETIME_TEST_CASE]


INVALID_SECONDS_INPUT = {"bk_timing": time.time() + 60, "force_check": True}
VALID_DATETIME_INPUT = {
    "bk_timing": (datetime.datetime.now() + datetime.timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S"),
    "force_check": True,
}
VALID_SECONDS_INPUT = {"bk_timing": 10, "force_check": True}
BUSINESS_TIMEZONE = zoneinfo.ZoneInfo(settings.TIME_ZONE)

# -------------------【Python 3.9+ 修改点】: 提前计算期望结果】-------------------
# 将字符串解析为 naive datetime 对象
_NAIVE_DATETIME = datetime.datetime.strptime(VALID_DATETIME_INPUT["bk_timing"], "%Y-%m-%d %H:%M:%S")
# 使用 .replace() 附加时区信息，得到我们期望的 aware datetime 对象
EXPECTED_AWARE_DATETIME = _NAIVE_DATETIME.replace(tzinfo=BUSINESS_TIMEZONE)
# -----------------------------------------------------------------

INVALID_SECONDS_TEST_CASE = ComponentTestCase(
    name="invalid seconds input test case",
    inputs=INVALID_SECONDS_INPUT,
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=False,
        outputs={
            "business_tz": BUSINESS_TIMEZONE,
            "ex_data": "输入参数%s不符合【秒(s) 或 时间(%%Y-%%m-%%d %%H:%%M:%%S)】格式" % INVALID_SECONDS_INPUT["bk_timing"],
        },
    ),
    schedule_assertion=None,
)

VALID_DATETIME_TEST_CASE = ComponentTestCase(
    name="valid datetime input test case",
    inputs=VALID_DATETIME_INPUT,
    parent_data={},
    execute_assertion=ExecuteAssertion(
        success=True,
        outputs={"business_tz": BUSINESS_TIMEZONE, "timing_time": EXPECTED_AWARE_DATETIME},
    ),
    schedule_assertion=ScheduleAssertion(
        success=True,
        outputs={"business_tz": BUSINESS_TIMEZONE, "timing_time": EXPECTED_AWARE_DATETIME},
        callback_data={},
    ),
)
