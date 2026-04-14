"""APIGW: update label."""

import json

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.label.models import Label
from bkflow.label.serializers import LabelSerializer, LabelUpdateSerializer
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@apigw_require
@check_jwt_and_space
@return_json_response
def update_label(request, space_id, label_id):
    data = json.loads(request.body or "{}")

    label = Label.objects.filter(id=label_id, space_id=int(space_id)).first()
    if label is None:
        return {
            "result": False,
            "data": None,
            "code": err_code.NOT_FOUND.code,
            "message": _(f"标签不存在: space_id={space_id}, label_id={label_id}"),
        }

    data["space_id"] = int(space_id)
    data["updated_by"] = request.user.username

    ser = LabelUpdateSerializer(instance=label, data=data, partial=True)
    ser.is_valid(raise_exception=True)
    label = ser.save()

    return {
        "result": True,
        "data": LabelSerializer(label).data,
        "code": err_code.SUCCESS.code,
    }
