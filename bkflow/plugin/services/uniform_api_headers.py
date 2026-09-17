"""读取空间已配置的插件来源 headers，不推断跨租户授权关系。"""

from bkflow.space.configs import UniformApiConfig, UniformAPIConfigHandler
from bkflow.space.models import SpaceConfig


def get_source_headers(space_id, source_key=None):
    """详情和 Schema 使用目录已有的 source_key；旧插件使用默认来源。"""
    raw_config = SpaceConfig.get_config(space_id=space_id, config_name=UniformApiConfig.name)
    if not raw_config:
        return {}
    config = UniformAPIConfigHandler(raw_config).handle()
    for api_key, entry in config.api.items():
        if source_key:
            matches = (entry.source_key or api_key) == source_key
        else:
            matches = api_key == UniformApiConfig.Keys.DEFAULT_API_KEY.value
        if matches:
            return dict(entry.headers or {})
    return {}
