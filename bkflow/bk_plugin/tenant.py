"""Interface 插件服务使用空间真实归属，单租户不增加查询或请求字段。"""

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import PermissionDenied


def get_plugin_tenant_id(space_id):
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return None
    from bkflow.space.models import Space

    tenant_id = Space.objects.filter(id=space_id, is_deleted=False).values_list("tenant_id", flat=True).first()
    if not tenant_id or not tenant_id.strip():
        raise PermissionDenied(_("插件查询空间缺少有效租户"))
    return tenant_id
