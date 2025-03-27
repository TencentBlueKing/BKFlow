import logging

from celery.app import shared_task
from rest_framework.exceptions import APIException

from bkflow.bk_plugin.models import BKPlugin
from plugin_service import env
from plugin_service.conf import PLUGIN_DISTRIBUTOR_NAME
from plugin_service.plugin_client import PluginServiceApiClient

logger = logging.getLogger("celery")


# 每十分钟执行一次增量同步
@shared_task()
def sync_bk_plugins():
    try:
        plugins_dict = fetch_newest_plugins_dict()
    except Exception as e:
        raise e
    BKPlugin.objects.bulk_update_bk_plugins(plugins_dict)


def fetch_newest_plugins_dict():
    """通过部署环境和授权app_code过滤蓝鲸插件，获取授权给bkflow的插件列表"""
    newest_plugins = {}
    offset = 0
    limit = 10
    while True:
        result = PluginServiceApiClient.get_plugin_detail_list(
            exclude_not_deployed=True,
            include_addresses=0,
            distributor_code_name=PLUGIN_DISTRIBUTOR_NAME,
        )
        if not result["data"]:
            raise APIException(result.get("message", "拉取蓝鲸插件列表失败"))
        newest_plugins.update(
            {
                plugin["plugin"]["code"]: plugin
                for _, plugin in enumerate(result["data"]["plugins"])
                if plugin["deployed_statuses"][env.APIGW_ENVIRONMENT]["deployed"]
            }
        )
        offset = offset + limit
        if result["data"]["count"] <= offset:
            break
    return newest_plugins
