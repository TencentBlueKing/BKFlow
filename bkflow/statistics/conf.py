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

from django.conf import settings

import env


class StatisticsConfig:
    """统计配置管理"""

    @classmethod
    def is_enabled(cls) -> bool:
        """是否启用统计功能"""
        return getattr(env, "STATISTICS_ENABLED", True)

    @classmethod
    def get_engine_id(cls) -> str:
        """获取当前 Engine 标识"""
        bkflow_module = getattr(settings, "BKFLOW_MODULE", None)
        if bkflow_module and hasattr(bkflow_module, "code"):
            return bkflow_module.code
        return getattr(env, "BKFLOW_MODULE_CODE", "default")

    @classmethod
    def get_db_alias(cls) -> str:
        """获取统计数据库别名"""
        if "statistics" in settings.DATABASES:
            return "statistics"
        return "default"

    @classmethod
    def should_collect_template_stats(cls) -> bool:
        """是否采集模板统计（Interface 模块执行）"""
        if not cls.is_enabled():
            return False
        # 只在 Interface 模块或未指定模块类型时采集模板统计
        module_type = getattr(env, "BKFLOW_MODULE_TYPE", "")
        return module_type in ("interface", "")

    @classmethod
    def should_collect_task_stats(cls) -> bool:
        """是否采集任务统计（Engine 模块执行）"""
        if not cls.is_enabled():
            return False
        # 只在 Engine 模块采集任务统计
        module_type = getattr(env, "BKFLOW_MODULE_TYPE", "")
        return module_type == "engine"

    @classmethod
    def include_mock_tasks(cls) -> bool:
        """是否统计 Mock 任务"""
        return getattr(env, "STATISTICS_INCLUDE_MOCK", False)

    @classmethod
    def include_deleted_tasks(cls) -> bool:
        """是否统计已删除任务"""
        return getattr(env, "STATISTICS_INCLUDE_DELETED", False)

    @classmethod
    def get_retention_days(cls) -> int:
        """获取统计数据保留天数"""
        return getattr(env, "STATISTICS_RETENTION_DAYS", 365)
