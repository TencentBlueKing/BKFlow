from django.conf import settings
from rest_framework import permissions

from bkflow.bk_plugin.models import BKPlugin


# 是否有插件的管理员权限
class BKPluginManagerPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if settings.BLOCK_ADMIN_PERMISSION:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if settings.BLOCK_ADMIN_PERMISSION:
            return False
        plugin = BKPlugin.objects.filter(code=obj.code).first()
        if not plugin.contact or request.user.username not in plugin.contact.split(","):
            return False
        return True
