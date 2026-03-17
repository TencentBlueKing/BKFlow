from django.conf import settings

import env


class StatisticsSettings:
    @classmethod
    def is_enabled(cls) -> bool:
        return getattr(env, "STATISTICS_ENABLED", True)

    @classmethod
    def get_engine_id(cls) -> str:
        bkflow_module = getattr(settings, "BKFLOW_MODULE", None)
        if bkflow_module and hasattr(bkflow_module, "code") and bkflow_module.code:
            return bkflow_module.code
        return getattr(env, "BKFLOW_MODULE_CODE", "default") or "default"

    @classmethod
    def get_db_alias(cls) -> str:
        if "statistics" in settings.DATABASES:
            return "statistics"
        return "default"

    @classmethod
    def get_module_type(cls) -> str:
        return getattr(env, "BKFLOW_MODULE_TYPE", "") or ""

    @classmethod
    def should_collect_template_stats(cls) -> bool:
        if not cls.is_enabled():
            return False
        return cls.get_module_type() in ("interface", "")

    @classmethod
    def should_collect_task_stats(cls) -> bool:
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
