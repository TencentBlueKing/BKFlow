"""保留 Django MySQL 后端，仅恢复已移除的 MySQL 5.7 兼容分支。"""

from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

from .features import DatabaseFeatures
from .operations import DatabaseOperations


class DatabaseWrapper(MySQLDatabaseWrapper):
    """为应用的 MySQL 连接提供默认兼容适配。"""

    features_class = DatabaseFeatures
    ops_class = DatabaseOperations
