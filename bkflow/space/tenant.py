"""Interface 的租户边界，独立于管理员、空间权限和 token 的 OR 组合。"""

from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from bkflow.utils.tenant import get_request_tenant_id


def tenant_space_ids(request):
    """返回当前用户租户的空间，平台管理员同样受此范围限制。"""
    from bkflow.space.models import Space

    spaces = Space.objects.filter(is_deleted=False)
    if settings.ENABLE_MULTI_TENANT_MODE:
        spaces = spaces.filter(tenant_id=get_request_tenant_id(request))
    return spaces.values_list("id", flat=True)


def ensure_space_tenant(request, space_id):
    """检查空间归属；返回空间租户供任务创建使用。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return "default"
    from bkflow.space.models import Space

    tenant_id = get_request_tenant_id(request)
    if not Space.objects.filter(id=space_id, tenant_id=tenant_id, is_deleted=False).exists():
        raise PermissionDenied("空间不存在或不属于当前租户")
    return tenant_id


def scope_queryset(request, queryset, allow_global_labels=False):
    """按资源的空间归属过滤；统计库通过已求值的空间 ID 避免跨库子查询。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return queryset
    from bkflow.space.models import Space
    from bkflow.template.models import Template

    fields = {field.name for field in queryset.model._meta.fields}
    space_ids = tenant_space_ids(request)
    if queryset.db != Space.objects.db:
        space_ids = list(space_ids)
    if queryset.model is Space:
        return queryset.filter(id__in=space_ids)
    if "space_id" in fields:
        condition = Q(space_id__in=space_ids)
        if allow_global_labels:
            condition |= Q(space_id=-1)
        return queryset.filter(condition)
    if "template_id" in fields:
        return queryset.filter(template_id__in=Template.objects.filter(space_id__in=space_ids).values("id"))
    return queryset


class TenantScopeMixin:
    """在读取请求参数及对象时强制租户检查，随后继续执行原有权限。"""

    tenant_internal_api = False
    tenant_allow_global_labels = False

    def _tenant_internal_request(self):
        # 仅标记为内部接口的视图可以使用模块凭证；普通用户接口不接受此绕过。
        token = getattr(self.request, "app_internal_token", None)
        return self.tenant_internal_api and bool(token) and token == settings.APP_INTERNAL_TOKEN

    def _tenant_enabled(self):
        return settings.ENABLE_MULTI_TENANT_MODE and not self._tenant_internal_request()

    def check_permissions(self, request):
        if self._tenant_enabled():
            get_request_tenant_id(request)
            self._check_tenant_parameters(request)
            queryset = getattr(self, "queryset", None)
            lookup_field = getattr(self, "lookup_field", "pk")
            lookup_kwarg = getattr(self, "lookup_url_kwarg", None) or lookup_field
            lookup = self.kwargs.get(lookup_kwarg)
            if queryset is not None and lookup is not None:
                targets = queryset.filter(**{lookup_field: lookup})
                if targets.exists() and not self._tenant_queryset(targets).exists():
                    raise PermissionDenied("资源不属于当前租户")
        super().check_permissions(request)

    def _check_tenant_parameters(self, request):
        from bkflow.template.models import Template, TemplateSnapshot

        sources = [self.kwargs, request.query_params, request.data]
        space_ids = {str(data["space_id"]) for data in sources if data.get("space_id") is not None}
        if len(space_ids) > 1:
            raise PermissionDenied("请求中的空间 ID 不一致")
        for space_id in space_ids:
            ensure_space_tenant(request, space_id)
        for field, model in (("template_id", Template), ("snapshot_id", TemplateSnapshot)):
            for data in sources:
                values = data.get(field + "s", [])
                if isinstance(values, str):
                    values = values.split(",")
                values = list(values)
                if data.get(field) is not None:
                    values.append(data[field])
                if not values:
                    continue
                targets = scope_queryset(request, model.objects.filter(pk__in=values))
                if space_ids:
                    if model is Template:
                        targets = targets.filter(space_id__in=space_ids)
                    else:
                        targets = targets.filter(
                            template_id__in=Template.objects.filter(space_id__in=space_ids).values("id")
                        )
                if targets.count() != len({str(value) for value in values}):
                    raise PermissionDenied("资源不存在或不属于当前租户")

    def _tenant_queryset(self, queryset):
        if not self._tenant_enabled():
            return queryset
        allow_global = self.tenant_allow_global_labels and self.request.method in ("GET", "HEAD", "OPTIONS")
        return scope_queryset(self.request, queryset, allow_global_labels=allow_global)

    def get_queryset(self):
        return self._tenant_queryset(super().get_queryset())

    def filter_queryset(self, queryset):
        return self._tenant_queryset(super().filter_queryset(queryset))

    def check_object_permissions(self, request, obj):
        if self._tenant_enabled() and not self._tenant_queryset(type(obj).objects.filter(pk=obj.pk)).exists():
            raise PermissionDenied("资源不属于当前租户")
        super().check_object_permissions(request, obj)
