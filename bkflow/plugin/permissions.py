from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from bkflow.permission.models import Token
from bkflow.space.configs import SuperusersConfig
from bkflow.space.models import SpaceConfig


def get_request_space_id(request):
    """POST 使用 body 空间，其他请求保持 query 优先。"""
    if request.method.upper() == "POST":
        query_space_id = request.query_params.get("space_id")
        body_space_id = request.data.get("space_id")
        if query_space_id is not None and body_space_id is not None and str(query_space_id) != str(body_space_id):
            raise PermissionDenied("query 与 body 的 space_id 不一致")
        return body_space_id
    return request.query_params.get("space_id") or request.data.get("space_id")


class PluginSpaceConsistencyPermission(permissions.BasePermission):
    """拒绝 POST query 与 body 中相互冲突的空间 ID。"""

    def has_permission(self, request, view):
        get_request_space_id(request)
        return True


class PluginTokenPermissions(permissions.BasePermission):
    """根据 token 判断用户请求的空间是否对应"""

    def has_permission(self, request, view):
        space_id = get_request_space_id(request)
        token = Token.objects.filter(token=request.token).first()
        if not token or token.has_expired():
            return False

        return int(token.space_id) == int(space_id or -1)


class PluginSpaceSuperuserPermission(permissions.BasePermission):
    """根据判断用户是否是请求空间管理员"""

    def has_permission(self, request, view):
        space_id = get_request_space_id(request)
        if not space_id:
            return False
        space_superusers = SpaceConfig.get_config(space_id, SuperusersConfig.name)
        is_space_superuser = request.user.username in space_superusers
        setattr(request, "is_space_superuser", is_space_superuser)
        return is_space_superuser
