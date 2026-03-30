from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bkflow.statistics"
    label = "statistics"
    verbose_name = "统计分析"

    def ready(self):
        self._configure_statistics_database()

        from bkflow.statistics.conf import StatisticsSettings

        if StatisticsSettings.is_enabled():
            try:
                from bkflow.statistics.signals.handlers import (
                    register_statistics_signals,
                )

                register_statistics_signals()
            except ImportError:
                pass

    @staticmethod
    def _configure_statistics_database():
        """当配置了 STATISTICS_DB_* 环境变量时，将统计数据库注入 settings.DATABASES。

        在 AppConfig.ready() 中执行，此时 settings.DATABASES 已被框架完全初始化，
        可以安全地往里添加新的数据库别名，不会覆盖 default 等已有配置。
        """
        from django.conf import settings

        import env

        if env.STATISTICS_DB_HOST and env.STATISTICS_DB_NAME:
            settings.DATABASES["statistics"] = {
                "ENGINE": "django.db.backends.mysql",
                "NAME": env.STATISTICS_DB_NAME,
                "USER": env.STATISTICS_DB_USER,
                "PASSWORD": env.STATISTICS_DB_PASSWORD,
                "HOST": env.STATISTICS_DB_HOST,
                "PORT": env.STATISTICS_DB_PORT,
            }
