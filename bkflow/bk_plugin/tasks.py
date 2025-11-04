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
import logging

from celery.app import shared_task
from rest_framework.exceptions import APIException

from bkflow.bk_plugin.models import BKPlugin
from bkflow.constants import BK_PLUGIN_SYNC_NUM
from plugin_service import env
from plugin_service.conf import PLUGIN_DISTRIBUTOR_NAME
from plugin_service.plugin_client import PluginServiceApiClient

logger = logging.getLogger("celery")


# 每十分钟执行一次增量同步
@shared_task()
def sync_bk_plugins():
    plugins_dict = {}
    try:
        plugins_dict = fetch_newest_plugins_dict()
    except APIException as e:
        logger.exception(f"同步蓝鲸插件列表时失败: {e}")
    BKPlugin.objects.sync_bk_plugins(plugins_dict)


def fetch_newest_plugins_dict():
    """通过部署环境和授权app_code过滤蓝鲸插件，获取授权给bkflow的插件列表"""
    plugins_dict = {}
    offset = 0
    limit = BK_PLUGIN_SYNC_NUM
    while True:
        result = PluginServiceApiClient.get_plugin_detail_list(
            exclude_not_deployed=True,
            include_addresses=0,
            distributor_code_name=PLUGIN_DISTRIBUTOR_NAME,
            limit=limit,
            offset=offset,
        )
        if not result["result"]:
            logger.exception(result.get("message", "拉取蓝鲸插件列表失败"))
            raise APIException(result.get("message", "拉取蓝鲸插件列表失败"))
        plugins_dict.update(
            {
                plugin["plugin"]["code"]: plugin
                for _, plugin in enumerate(result["data"]["plugins"])
                if plugin["deployed_statuses"][env.APIGW_ENVIRONMENT]["deployed"]
            }
        )
        offset = offset + limit
        if result["data"]["count"] <= offset:
            logger.info(f"拉取蓝鲸插件列表成功，共{len(plugins_dict.keys())}个")
            break
    return plugins_dict
