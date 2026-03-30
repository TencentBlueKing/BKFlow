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
