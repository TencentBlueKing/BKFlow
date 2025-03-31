from rest_framework import permissions

from bkflow.bk_plugin.models import BKPlugin


# 是否有插件的管理员权限
class BKPluginManagerPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        plugin = BKPlugin.objects.filter(code=obj.code).first()
        if not plugin.manager or request.user.username not in plugin.manager:
            return False
        return True
