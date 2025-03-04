# -*- coding: utf-8 -*-
from rest_framework import permissions

from bkflow.permission.models import Token
from bkflow.space.configs import SuperusersConfig
from bkflow.space.models import SpaceConfig


class PluginTokenPermissions(permissions.BasePermission):
    """根据 token 判断用户请求的空间是否对应"""

    def has_permission(self, request, view):
        token = Token.objects.filter(token=request.token).first()
        if not token or token.has_expired():
            return False

        return int(token.space_id) == int(request.query_params.get("space_id", -1))


class PluginSpaceSuperuserPermission(permissions.BasePermission):
    """根据判断用户是否是请求空间管理员"""

    def has_permission(self, request, view):
        space_id = request.query_params.get("space_id")
        if not space_id:
            return False
        space_superusers = SpaceConfig.get_config(space_id, SuperusersConfig.name)
        is_space_superuser = request.user.username in space_superusers
        setattr(request, "is_space_superuser", is_space_superuser)
        return is_space_superuser
