from django import template

from bkflow.admin.models import ModuleInfo

register = template.Library()


@register.simple_tag
def get_engine_modules():
    """Return all engine modules with pre-built admin URLs for template rendering.
    Uses get_isolation_level_display() to show human-readable isolation level."""
    return [
        {
            "code": m.code,
            "space_id": m.space_id,
            "isolation_level": m.get_isolation_level_display(),
            "admin_url": f"{m.url.rstrip('/')}/bkflow_admin/" if m.url else "",
        }
        for m in ModuleInfo.objects.all()
    ]
