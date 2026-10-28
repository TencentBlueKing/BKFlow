"""恢复 MySQL 5.7 支持的正则表达式 SQL。"""

from django.db.backends.mysql.operations import (
    DatabaseOperations as MySQLDatabaseOperations,
)


class DatabaseOperations(MySQLDatabaseOperations):
    """避免在 MySQL 5.7 上生成 MySQL 8 才提供的 REGEXP_LIKE。"""

    def regex_lookup(self, lookup_type):
        """保留 regex 大小写敏感、iregex 大小写不敏感的原有语义。"""
        if not self.connection.mysql_is_mariadb and self.connection.mysql_version < (8,):
            return "%s REGEXP BINARY %s" if lookup_type == "regex" else "%s REGEXP %s"
        return super().regex_lookup(lookup_type)
