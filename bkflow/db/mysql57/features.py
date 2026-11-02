"""恢复 Django 4.1 中 MySQL 5.7 仍需使用的 SQL 能力声明。"""

from django.db.backends.mysql.features import DatabaseFeatures as MySQLDatabaseFeatures
from django.utils.functional import cached_property


class DatabaseFeatures(MySQLDatabaseFeatures):
    """仅调整 MySQL 5.7，保留 MySQL 8 和 MariaDB 的原有行为。"""

    @cached_property
    def minimum_database_version(self):
        """接受已验证的 MySQL 5.7.20+，不放宽 MariaDB 的最低版本。"""
        if not self.connection.mysql_is_mariadb:
            return (5, 7, 20)
        return super().minimum_database_version

    @cached_property
    def bare_select_suffix(self):
        """MySQL 5.7 的无表 SELECT 带 WHERE 时仍要求 FROM DUAL。"""
        if not self.connection.mysql_is_mariadb and self.connection.mysql_version < (8,):
            return " FROM DUAL"
        return super().bare_select_suffix
