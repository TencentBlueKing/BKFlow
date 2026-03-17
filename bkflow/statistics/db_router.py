class StatisticsDBRouter:
    APP_LABEL = "statistics"
    DB_ALIAS = "statistics"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.APP_LABEL:
            return self._get_db_alias()
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.APP_LABEL:
            return self._get_db_alias()
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == self.APP_LABEL and obj2._meta.app_label == self.APP_LABEL:
            return True
        if obj1._meta.app_label == self.APP_LABEL or obj2._meta.app_label == self.APP_LABEL:
            return False
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.APP_LABEL:
            return db == self._get_db_alias()
        return db != self.DB_ALIAS

    def _get_db_alias(self):
        from django.conf import settings

        if self.DB_ALIAS in settings.DATABASES:
            return self.DB_ALIAS
        return "default"
