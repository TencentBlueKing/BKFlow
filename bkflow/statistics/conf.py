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

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone

import env


def date_to_datetime_range(d: date) -> tuple:
    """将 date 转为当天 00:00:00 ~ 次日 00:00:00 的 timezone-aware datetime 范围。

    用于替代 Django ORM 的 ``__date`` lookup，避免 MySQL 未加载时区数据时
    ``CONVERT_TZ`` 返回 NULL 导致查询失效的问题。

    :return: (day_start, day_end) 均为 aware datetime
    """
    day_start = timezone.make_aware(datetime.combine(d, time.min))
    day_end = timezone.make_aware(datetime.combine(d, time.min)) + timedelta(days=1)
    return day_start, day_end


class StatisticsSettings:
    """统计模块配置中心，提供各项配置的统一访问入口"""

    @classmethod
    def is_enabled(cls) -> bool:
        """统计功能总开关"""
        return getattr(env, "STATISTICS_ENABLED", True)

    @classmethod
    def get_engine_id(cls) -> str:
        """获取当前引擎实例标识，用于多引擎部署时区分数据来源"""
        bkflow_module = getattr(settings, "BKFLOW_MODULE", None)
        if bkflow_module and hasattr(bkflow_module, "code") and bkflow_module.code:
            return bkflow_module.code
        return getattr(env, "BKFLOW_MODULE_CODE", "default") or "default"

    @classmethod
    def get_db_alias(cls) -> str:
        """获取统计数据库别名，若未配置独立的 statistics 数据库则回退到 default"""
        if "statistics" in settings.DATABASES:
            return "statistics"
        return "default"

    @classmethod
    def get_module_type(cls) -> str:
        """获取当前模块类型，决定该模块负责采集哪些维度的统计数据"""
        return getattr(env, "BKFLOW_MODULE_TYPE", "") or ""

    @classmethod
    def should_collect_template_stats(cls) -> bool:
        """是否应采集模板统计，仅 interface 模块或单模块部署时启用"""
        if not cls.is_enabled():
            return False
        return cls.get_module_type() in ("interface", "")

    @classmethod
    def should_collect_task_stats(cls) -> bool:
        """是否应采集任务统计，仅 engine 模块时启用（单模块部署由模板统计覆盖）"""
        if not cls.is_enabled():
            return False
        return cls.get_module_type() == "engine"

    @classmethod
    def include_mock_tasks(cls) -> bool:
        return getattr(env, "STATISTICS_INCLUDE_MOCK", False)

    @classmethod
    def get_detail_retention_days(cls) -> int:
        return getattr(env, "STATISTICS_DETAIL_RETENTION_DAYS", 90)

    @classmethod
    def get_summary_retention_days(cls) -> int:
        return getattr(env, "STATISTICS_SUMMARY_RETENTION_DAYS", 365)
