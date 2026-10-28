"""在最终数据库配置加载后默认使用 MySQL 5.7 兼容后端。"""

from django import VERSION
from django.core.exceptions import ImproperlyConfigured

MYSQL_BACKEND = "django.db.backends.mysql"
MYSQL57_BACKEND = "bkflow.db.mysql57"


def configure_mysql57_compat(databases):
    """仅替换原生 MySQL 后端，保留所有连接参数和其他自定义后端。

    同时为每个数据库连接补全 Django 4.2 必需的 ATOMIC_REQUESTS 键：
    django/core/handlers/base.py 的 make_view_atomic 会直接以
    settings_dict["ATOMIC_REQUESTS"] 方式读取该键（不带默认值），若手写
    DATABASES 配置时遗漏该键会触发 KeyError，因此在此统一补全默认值。
    """
    if VERSION[:2] != (4, 2):
        raise ImproperlyConfigured("The MySQL 5.7 compatibility backend requires Django 4.2.")
    result = {}
    for alias, config in databases.items():
        # 补全 ATOMIC_REQUESTS 默认值，避免 Django 4.2 make_view_atomic 的 KeyError
        config = {**config, "ATOMIC_REQUESTS": config.get("ATOMIC_REQUESTS", False)}
        if config.get("ENGINE") == MYSQL_BACKEND:
            config = {**config, "ENGINE": MYSQL57_BACKEND}
        result[alias] = config
    return result
