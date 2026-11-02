"""在最终数据库配置加载后默认使用 MySQL 5.7 兼容后端。"""

from django import VERSION
from django.core.exceptions import ImproperlyConfigured

MYSQL_BACKEND = "django.db.backends.mysql"
MYSQL57_BACKEND = "bkflow.db.mysql57"


def configure_mysql57_compat(databases):
    """仅替换原生 MySQL 后端，保留所有连接参数和其他自定义后端。"""
    if not any(config.get("ENGINE") == MYSQL_BACKEND for config in databases.values()):
        return databases
    if VERSION[:2] != (4, 2):
        raise ImproperlyConfigured("The MySQL 5.7 compatibility backend requires Django 4.2.")
    return {
        alias: {**config, "ENGINE": MYSQL57_BACKEND} if config.get("ENGINE") == MYSQL_BACKEND else config
        for alias, config in databases.items()
    }
