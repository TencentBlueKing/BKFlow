"""统计模块配置管理

通过环境变量和 Django settings 控制统计模块的行为：
- STATISTICS_ENABLED: 是否启用统计（默认 True）
- BKFLOW_MODULE_TYPE: 模块类型，决定采集哪些维度的数据
  - "interface": 采集模板统计（模板管理接口所在模块）
  - "engine": 采集任务统计（引擎执行所在模块）
  - "": 同时采集模板和任务统计（单模块部署）
- STATISTICS_INCLUDE_MOCK: 是否统计 Mock 任务
- STATISTICS_DETAIL_RETENTION_DAYS: 明细数据保留天数（默认 90）
- STATISTICS_SUMMARY_RETENTION_DAYS: 汇总数据保留天数（默认 365）
"""

from datetime import date, datetime, time

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
    day_end = timezone.make_aware(datetime.combine(d, time.min)) + timezone.timedelta(days=1)
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
