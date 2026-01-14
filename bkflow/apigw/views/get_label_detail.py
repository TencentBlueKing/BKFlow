"""APIGW: label detail."""

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db.models import Exists, OuterRef
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.label.models import Label
from bkflow.label.serializers import LabelSerializer
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_label_detail(request, space_id, label_id):
    label = Label.objects.filter(id=label_id, space_id__in=[-1, int(space_id)]).first()
    if label is None:
        return {
            "result": False,
            "data": None,
            "code": err_code.NOT_FOUND.code,
            "message": _(f"标签不存在: label_id={label_id}"),
        }

    child_subquery = Label.objects.filter(parent_id=OuterRef("pk"))
    label = Label.objects.filter(pk=label.pk).annotate(has_children=Exists(child_subquery)).first()

    return {
        "result": True,
        "data": LabelSerializer(label).data,
        "code": err_code.SUCCESS.code,
    }
