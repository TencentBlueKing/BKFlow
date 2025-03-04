# -*- coding: utf-8 -*-
from rest_framework import permissions

from bkflow.permission.models import Token


class TokenPluginPermissions(permissions.BasePermission):
    """根据 token 判断用户请求的空间是否对应"""

    def has_permission(self, request, view):
        token = Token.objects.filter(token=request.token).first()
        if not token or token.has_expired():
            return False

        return int(token.space_id) == int(request.query_params.get("space_id", -1))
