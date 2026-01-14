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
import json
import logging
from typing import Dict

from django.conf import settings

from bkflow.contrib.api.collections.interface import InterfaceModuleClient
from bkflow.utils.singleton import Singleton

logger = logging.getLogger("root")


class SpaceConfigManager(metaclass=Singleton):
    """空间配置管理器"""

    def __init__(self):
        self._cache_duration = 60
        self._interface_client = InterfaceModuleClient()

    def get_space_config(self, space_id: str, config_names: str) -> Dict:
        """获取空间配置，支持缓存"""
        # cache_key = f"{space_id}:{config_names}"
        cache_key = f"space_config:{space_id}:{config_names}"

        cached_data = settings.redis_inst.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        try:
            space_infos_result = self._interface_client.get_space_infos(
                {"space_id": space_id, "config_names": config_names}
            )

            if space_infos_result.get("result"):
                space_configs = space_infos_result.get("data", {}).get("configs", {})

                settings.redis_inst.setex(cache_key, self._cache_duration, json.dumps(space_configs))
                return space_configs
            else:
                logger.error(f"获取空间配置失败: space_id={space_id}, error={space_infos_result.get('message')}")
                return {}

        except Exception as e:
            logger.error(f"获取空间配置异常: space_id={space_id}, error={e}")
            return {}

    def get_concurrency_control(self, space_id: str) -> int:
        space_configs = self.get_space_config(space_id, "concurrency_control")
        return int(space_configs.get("concurrency_control", 0))


space_config_manager = SpaceConfigManager()
