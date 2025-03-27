import logging
from datetime import datetime

from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.bk_plugin.models import AuthorizeStatus, BKPlugin, BKPluginAuthentication
from bkflow.bk_plugin.permissions import BKPluginManagerPermission
from bkflow.bk_plugin.serializer import (
    AuthQuerySerializer,
    BKPluginAuthSerializer,
    BKPluginSerializer,
    UpdateAuthConfigSerializer,
)
from bkflow.space.permissions import SpaceSuperuserPermission
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import ReadOnlyViewSet, SimpleGenericViewSet

logger = logging.getLogger("root")


class BKPluginAdminViewSet(ReadOnlyViewSet):
    queryset = BKPluginAuthentication.objects.all()
    serializer_class = BKPluginAuthSerializer
    permission_classes = [AdminPermission | SpaceSuperuserPermission]
    lookup_field = "code"

    def list(self, request, *args, **kwargs):
        plugins = BKPlugin.objects.get_plugin_by_manager(request.user.username)
        plugin_codes = [plugin.code for plugin in plugins]
        queryset = self.get_queryset().filter(code__in=plugin_codes)
        serializer = self.get_serializer(queryset, many=True)
        return Response(data={"count": len(serializer.data), "plugins": serializer.data})

    @action(detail=True, methods=["get"], url_path="change_auth", permission_classes=[BKPluginManagerPermission])
    def change_auth_status(self, request, code):
        target_plugin = self.get_object()
        # 与1进行异或运算， 0^1=1, 1^1=0
        target_plugin.status ^= 1
        if target_plugin.status == AuthorizeStatus.authorized:
            target_plugin.authorized_time = datetime.now()
            target_plugin.operator = request.user.username
        target_plugin.save()
        return Response(data=f"插件{code}的授权状态更改成功，当前授权状态:{target_plugin.status}")

    @swagger_auto_schema(method="post", operation_summary="更改授权配置", request_body=UpdateAuthConfigSerializer)
    @action(detail=True, methods=["post"], url_path="update_config", permission_classes=[BKPluginManagerPermission])
    def update_config(self, request, *args, **kwargs):
        plugin = self.get_object()
        serializer = UpdateAuthConfigSerializer(
            plugin, data=request.data, partial=True, context={"username": request.user.username}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": f"{plugin.code}授权配置更新成功"})


class BKPluginViewSet(SimpleGenericViewSet):
    queryset = BKPlugin.objects.all()
    serializer_class = BKPluginSerializer
    permission_classes = [AdminPermission]

    @swagger_auto_schema(
        method="get", operation_summary="根据tag和space_id获取已授权的插件列表", query_serializer=AuthQuerySerializer
    )
    @action(detail=False, methods=["get"], url_path="authorized_list")
    def get_authorized_list(self, request):
        tag = request.query_params.get("tag")
        space_id = request.query_params.get("space_id")
        if not tag or not space_id:
            return Response({"result": "False", "message": "参数错误:请传入tag和space_id"})
        plugins_queryset = self.get_queryset().filter(tag=tag)
        auth_codes = BKPluginAuthentication.objects.get_codes_by_space_id(space_id)
        plugins_queryset = plugins_queryset.filter(code__in=auth_codes)
        serializer = BKPluginSerializer(plugins_queryset, many=True)
        return Response({"count": len(serializer.data), "plugins": serializer.data})
