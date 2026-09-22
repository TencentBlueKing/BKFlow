"""Interface 内的流程引用归属校验，不依赖用户可修改的流程树租户字段。"""

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError


def validate_template_references(space_id, pipeline_tree):
    """多租户下校验嵌套子流程；单租户保留已有流程协议和引用行为。"""
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return
    from bkflow.template.models import Template

    template_ids = set()
    trees = [pipeline_tree]
    while trees:
        tree = trees.pop()
        for activity in tree.get("activities", {}).values():
            reference = None
            if activity.get("type") == "SubProcess":
                reference = activity
            elif activity.get("component", {}).get("code") == "subprocess_plugin":
                reference = activity["component"].get("data", {}).get("subprocess", {}).get("value")
                if not isinstance(reference, dict):
                    raise ValidationError(_("子流程必须指定固定的模板引用"))
            if reference is not None:
                template_id = reference.get("template_id")
                if isinstance(template_id, bool) or not str(template_id).isdigit() or int(template_id) <= 0:
                    raise ValidationError(_("子流程模板 ID 无效"))
                template_ids.add(int(template_id))
            if isinstance(activity.get("pipeline"), dict):
                trees.append(activity["pipeline"])
    if not template_ids:
        return
    if not space_id or Template.objects.filter(id__in=template_ids, space_id=space_id, is_deleted=False).count() != len(
        template_ids
    ):
        raise ValidationError(_("子流程模板不存在或不属于当前空间"))
