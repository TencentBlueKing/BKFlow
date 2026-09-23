"""APIGW: delete label."""

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.label.models import Label, TemplateLabelRelation
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def delete_label(request, space_id, label_id):
    label = Label.objects.filter(id=label_id, space_id=int(space_id)).first()
    if label:
        need_delete_label_ids = [label.id]
        if label.parent_id is None:
            sub_label_ids = Label.objects.filter(parent_id=label.id).values_list("id", flat=True)
            need_delete_label_ids.extend(list(sub_label_ids))

        client = TaskComponentClient(space_id=int(space_id))
        result = client.delete_task_label_relation({"label_ids": need_delete_label_ids})
        if not result.get("result"):
            return {
                "result": False,
                "data": result.get("data"),
                "code": err_code.VALIDATION_ERROR.code,
                "message": result.get("message"),
            }

        TemplateLabelRelation.objects.filter(label_id__in=need_delete_label_ids).delete()
        Label.objects.filter(id__in=need_delete_label_ids).delete()

    return {"result": True, "data": {}, "code": err_code.SUCCESS.code}
