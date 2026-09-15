"""租户身份解析、升级兼容与 Engine 的内部调用边界。"""

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied


class TenantIDField(serializers.CharField):
    """单租户旧请求省略租户时使用历史默认值；多租户仍要求显式传入。"""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 32)
        super().__init__(**kwargs)

    def validate_empty_values(self, data):
        if data is serializers.empty and not settings.ENABLE_MULTI_TENANT_MODE and not self.root.partial:
            return True, "default"
        return super().validate_empty_values(data)

    def run_validation(self, data=serializers.empty):
        # 旧登录用户的 tenant_id 可能为空；仅在单租户模式兼容该输入。
        if not settings.ENABLE_MULTI_TENANT_MODE and isinstance(data, str) and not data.strip():
            data = "default"
        return super().run_validation(data)


def get_request_tenant_id(request):
    """取得用户当前身份的租户，禁止缺失身份时回退到 system 或单租户协议。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return "default"
    tenant_id = getattr(getattr(request, "user", None), "tenant_id", None)
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise PermissionDenied("当前用户缺少租户身份")
    jwt = getattr(request, "jwt", None)
    if jwt:
        jwt_user = jwt.payload.get("user") or {}
        if jwt_user.get("verified") and jwt_user.get("tenant_id") != tenant_id:
            raise PermissionDenied("登录身份与网关用户租户不一致")
        if getattr(getattr(request, "app", None), "verified", False):
            if get_apigw_request_tenant_id(request) != tenant_id:
                raise PermissionDenied("用户租户与应用本次请求租户不一致")
    return tenant_id


def get_apigw_request_tenant_id(request):
    """应用态不依赖用户：已认证全租户应用选租户，单租户应用受 JWT 归属约束。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return "default"
    app = getattr(request, "app", None)
    if not app or not app.verified:
        raise PermissionDenied("缺少已认证的网关应用身份")
    mode = getattr(app, "tenant_mode", None)
    app_tenant = getattr(app, "tenant_id", None)
    header_tenant = request.headers.get("X-Bk-Tenant-Id")
    if mode == "global":
        # 全租户应用有权选择任意租户；该请求头只选择范围，不授予应用身份或资源权限。
        tenant_id = header_tenant
    elif mode == "single":
        tenant_id = app_tenant
        if header_tenant is not None and header_tenant != app_tenant:
            raise PermissionDenied("请求租户与应用所属租户不一致")
    else:
        raise PermissionDenied("应用缺少有效的租户模式")
    if not isinstance(tenant_id, str) or not tenant_id.strip() or len(tenant_id) > 32:
        raise PermissionDenied("应用请求缺少有效的租户 ID")
    jwt = getattr(request, "jwt", None)
    jwt_user = jwt.payload.get("user", {}) if jwt else {}
    if jwt_user and jwt_user.get("verified") and jwt_user.get("tenant_id") != tenant_id:
        raise PermissionDenied("网关用户租户与应用本次请求租户不一致")
    return tenant_id


def get_task_tenant_id(parent_data):
    """兼容升级前已持久化且没有租户字段的 Pipeline 上下文，仅查询所属 Engine。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return "default"
    tenant_id = parent_data.get_one_of_inputs("tenant_id")
    if tenant_id:
        return tenant_id
    from bkflow.task.models import TaskInstance

    task_id = parent_data.get_one_of_inputs("task_id")
    tenant_id = TaskInstance.objects.only("tenant_id").get(pk=task_id).tenant_id
    if not tenant_id:
        raise PermissionDenied("任务缺少租户归属，请先完成存量数据回填")
    return tenant_id


class EngineTenantScopeMixin:
    """Engine 用户操作经 Interface 授权；内部请求仍绑定传入的空间。"""

    def check_permissions(self, request):
        if settings.ENABLE_MULTI_TENANT_MODE:
            token = getattr(request, "app_internal_token", None)
            if not token or token != settings.APP_INTERNAL_TOKEN:
                raise PermissionDenied("多租户 Engine 接口仅接受已认证的模块调用")
            space_id = request.headers.get(settings.APP_INTERNAL_SPACE_ID_HEADER_KEY)
            if not space_id or not str(space_id).isdigit():
                raise PermissionDenied("模块调用缺少有效的空间 ID")
            if space_id != "0":
                sources = [request.query_params, request.data]
                if isinstance(request.data.get("config"), dict):
                    sources.append(request.data["config"])
                for data in sources:
                    if data.get("space_id") is not None and str(data["space_id"]) != str(space_id):
                        raise PermissionDenied("请求空间与内部调用空间不一致")
        super().check_permissions(request)

    def get_queryset(self):
        queryset = super().get_queryset()
        if settings.ENABLE_MULTI_TENANT_MODE:
            space_id = self.request.headers.get(settings.APP_INTERNAL_SPACE_ID_HEADER_KEY)
            if space_id and space_id != "0":
                fields = {field.name for field in queryset.model._meta.fields}
                lookup = "space_id" if "space_id" in fields else "config__space_id"
                queryset = queryset.filter(**{lookup: int(space_id)})
        return queryset
