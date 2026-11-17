"""APIGW: label reference counts."""

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.label import LabelRefCountSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.label.models import Label, TemplateLabelRelation
from bkflow.template.models import Template
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_label_ref_count(request, space_id):
    ser = LabelRefCountSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)

    label_ids = ser.validated_data["label_ids"].split(",")
    scope_type = ser.validated_data.get("scope_type")
    scope_value = ser.validated_data.get("scope_value")

    all_child = Label.objects.filter(space_id=int(space_id), parent_id__in=label_ids).values("id", "parent_id")
    label_child_map = {}
    for item in all_child:
        pid = str(item["parent_id"])
        label_child_map.setdefault(pid, []).append(str(item["id"]))

    all_query_label_ids = list(set(label_ids + [cid for ids in label_child_map.values() for cid in ids]))

    client = TaskComponentClient(space_id=int(space_id))
    task_result = client.get_task_label_ref_count(int(space_id), ",".join(all_query_label_ids), scope_type, scope_value)
    if not task_result.get("result"):
        return task_result
    label_task_ref_count_map = task_result.get("data") or {}

    # 仅统计属于当前空间、且流程作用域匹配的模板，避免统计到其他空间或作用域的引用
    space_template_filter = {"space_id": int(space_id)}
    if scope_type is not None and scope_value is not None:
        space_template_filter["scope_type"] = scope_type
        space_template_filter["scope_value"] = scope_value
    space_template_ids = Template.objects.filter(**space_template_filter).values_list("id", flat=True)

    aggregation_qs = (
        TemplateLabelRelation.objects.filter(label_id__in=all_query_label_ids)
        .filter(template_id__in=space_template_ids)
        .values("label_id")
        .annotate(count=Count("id"))
    )
    label_template_count_map = {item["label_id"]: item["count"] for item in aggregation_qs}

    ref_result = {}
    for label_id in label_ids:
        if label_id in label_child_map:
            child_ids = label_child_map[label_id]
            template_count = sum(label_template_count_map.get(int(cid), 0) for cid in child_ids)
            task_count = sum(label_task_ref_count_map.get(str(cid), 0) for cid in child_ids)
        else:
            template_count = label_template_count_map.get(int(label_id), 0)
            task_count = label_task_ref_count_map.get(label_id, 0)

        ref_result[label_id] = {"template_count": template_count, "task_count": task_count}

    return {"result": True, "data": ref_result, "code": err_code.SUCCESS.code}
