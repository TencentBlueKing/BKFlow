"""选择平台 API 协议，独立保留上云旧平台的单租户兼容配置。"""

from django.conf import settings


def use_apigw():
    """新平台的单租户也使用 APIGW，多租户始终使用支持租户的接口。"""
    return settings.ENABLE_MULTI_TENANT_MODE or settings.BKFLOW_PLATFORM_API_MODE == "apigw"
