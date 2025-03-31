import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

import env
from bkflow.bk_plugin.models import BKPlugin, BKPluginAuthorization
from bkflow.bk_plugin.permissions import BKPluginManagerPermission
from bkflow.bk_plugin.serializer import (
    AuthListSerializer,
    BKPluginAuthSerializer,
    BKPluginSerializer,
)
from bkflow.exceptions import ValidationError
from bkflow.utils.mixins import BKFLOWNoMaxLimitPagination
from bkflow.utils.permissions import AdminPermission
from bkflow.utils.views import ReadOnlyViewSet, SimpleGenericViewSet

logger = logging.getLogger("root")


class BKPluginManagerViewSet(ReadOnlyViewSet, mixins.UpdateModelMixin):
    queryset = BKPluginAuthorization.objects.all()
    serializer_class = BKPluginAuthSerializer
    pagination_class = BKFLOWNoMaxLimitPagination
    permission_classes = [AdminPermission & BKPluginManagerPermission]
    lookup_field = "code"

    def list(self, request, *args, **kwargs):
        plugins = BKPlugin.objects.get_plugin_by_manager(request.user.username)
        paged_data = self.pagination_class().paginate_queryset(plugins, request)
        serializer = AuthListSerializer(data=paged_data, many=True)
        serializer.is_valid()
        return Response(data={"total_count": len(plugins), "plugins": serializer.data})

    def update(self, request, *args, **kwargs):
        authorization = self.get_queryset().filter(code=kwargs.get("code")).first()
        if not authorization:
            BKPluginAuthorization.objects.create(code=kwargs.get("code"))
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "status" in serializer.validated_data:
            serializer.context.update({"username": request.user.username})
        try:
            serializer.save()
        except ValidationError as e:
            return Response({"result": False, "message": e.message})
        return Response({"message": "更新成功", "data": serializer.data})


class BKPluginViewSet(SimpleGenericViewSet):
    queryset = BKPlugin.objects.all()
    serializer_class = BKPluginSerializer
    pagination_class = BKFLOWNoMaxLimitPagination
    permission_classes = []

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter("tag", openapi.IN_QUERY, description="插件分类", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter(
                "space_id", openapi.IN_QUERY, description="当前空间ID", type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter("limit", openapi.IN_QUERY, description="每页数量", type=openapi.TYPE_INTEGER),
            openapi.Parameter("offset", openapi.IN_QUERY, description="起始位置", type=openapi.TYPE_INTEGER),
        ]
    )
    def list(self, request):
        tag = request.query_params.get("tag")
        space_id = request.query_params.get("space_id")
        if not tag or not space_id:
            return Response({"result": False, "message": "参数错误:请传入tag和space_id"})
        plugins_queryset = self.get_queryset().filter(tag=int(tag))
        if env.USE_BK_PLUGIN_AUTHORIZATION:
            authorized_codes = BKPluginAuthorization.objects.get_codes_by_space_id(int(space_id))
            plugins_queryset = plugins_queryset.filter(code__in=authorized_codes)
        paged_data = self.pagination_class().paginate_queryset(plugins_queryset, request)
        serializer = self.get_serializer(paged_data, many=True)
        return Response({"total_count": len(plugins_queryset), "plugins": serializer.data})

    @action(detail=False, methods=["GET"], url_path="is_manager", pagination_class=None)
    def is_manager(self, request):
        return Response(self.get_queryset().filter(manager__contains=request.user.username).exists())
