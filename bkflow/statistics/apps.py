from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bkflow.statistics"
    label = "statistics"
    verbose_name = "统计分析"

    def ready(self):
        from bkflow.statistics.conf import StatisticsSettings

        if StatisticsSettings.is_enabled():
            try:
                from bkflow.statistics.signals.handlers import (
                    register_statistics_signals,
                )

                register_statistics_signals()
            except ImportError:
                pass
