"""多租户升级兼容；不在此定义资源授权和跨租户访问策略。"""

from django.conf import settings
from rest_framework import serializers


class TenantIDField(serializers.CharField):
    """单租户旧请求省略租户时使用历史默认值；多租户仍要求显式传入。"""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 32)
        super().__init__(**kwargs)

    def validate_empty_values(self, data):
        if data is serializers.empty and not settings.ENABLE_MULTI_TENANT_MODE and not self.root.partial:
            return True, "default"
        return super().validate_empty_values(data)


def get_task_tenant_id(parent_data):
    """兼容升级前已持久化且没有租户字段的 Pipeline 上下文，仅查询所属 Engine。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return "default"
    tenant_id = parent_data.get_one_of_inputs("tenant_id")
    if tenant_id:
        return tenant_id
    from bkflow.task.models import TaskInstance

    task_id = parent_data.get_one_of_inputs("task_id")
    return TaskInstance.objects.only("tenant_id").get(pk=task_id).tenant_id
