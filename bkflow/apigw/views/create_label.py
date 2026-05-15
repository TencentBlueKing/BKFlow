"""APIGW: create label."""

import json

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.label.models import Label
from bkflow.label.serializers import LabelCreateSerializer, LabelSerializer
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_POST
@apigw_require
@check_jwt_and_space
@return_json_response
def create_label(request, space_id):
    data = json.loads(request.body or "{}")
    data["space_id"] = int(space_id)

    username = request.user.username
    data.setdefault("creator", username)
    data.setdefault("updated_by", username)

    name = (data.get("name") or "").strip()
    name_parts = [p.strip() for p in name.split("/") if p.strip()]

    # Support 'parent/child' creation
    if len(name_parts) == 2:
        parent_name, child_name = name_parts

        parent_label = Label.objects.filter(name=parent_name, space_id=int(space_id), parent_id__isnull=True).first()
        if parent_label is None:
            parent_data = dict(data)
            parent_data["name"] = parent_name
            parent_data.pop("parent_id", None)

            parent_ser = LabelCreateSerializer(data=parent_data)
            parent_ser.is_valid(raise_exception=True)
            parent_label = parent_ser.save()

        data["parent_id"] = parent_label.id
        data["name"] = child_name

    ser = LabelCreateSerializer(data=data)
    ser.is_valid(raise_exception=True)
    label = ser.save()

    return {
        "result": True,
        "data": LabelSerializer(label).data,
        "code": err_code.SUCCESS.code,
        "message": _("success"),
    }
