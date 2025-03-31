import logging

from celery.app import shared_task
from rest_framework.exceptions import APIException

from bkflow.bk_plugin.models import BKPlugin
from bkflow.constants import MAX_LIMIT_OF_SYNC
from plugin_service import env
from plugin_service.conf import PLUGIN_DISTRIBUTOR_NAME
from plugin_service.plugin_client import PluginServiceApiClient

logger = logging.getLogger("celery")


# 每十分钟执行一次增量同步
@shared_task()
def sync_bk_plugins():
    plugins_dict = fetch_newest_plugins_dict()
    BKPlugin.objects.sync_bk_plugins(plugins_dict)


def fetch_newest_plugins_dict():
    """通过部署环境和授权app_code过滤蓝鲸插件，获取授权给bkflow的插件列表"""
    plugins_dict = {}
    offset = 0
    limit = MAX_LIMIT_OF_SYNC  # 最大多少可以测试一下
    while True:
        result = PluginServiceApiClient.get_plugin_detail_list(
            exclude_not_deployed=True,
            include_addresses=0,
            distributor_code_name=PLUGIN_DISTRIBUTOR_NAME,
        )
        if not result["data"]:
            logger.error(result.get("message", "拉取蓝鲸插件列表失败"))
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
            break
    return plugins_dict
