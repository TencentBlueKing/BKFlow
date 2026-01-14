"""APIGW: label list."""

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db.models import Exists, OuterRef, Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.label import LabelListFilterSerializer
from bkflow.apigw.utils import paginate_list_data
from bkflow.label.models import Label
from bkflow.label.serializers import LabelSerializer
from bkflow.utils import err_code


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_label_list(request, space_id):
    ser = LabelListFilterSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)

    params = dict(ser.validated_data)
    order_by = params.pop("order_by", "-updated_at")

    queryset = Label.objects.filter(space_id__in=[-1, int(space_id)]).order_by(order_by)

    label_scope = params.get("label_scope")
    if label_scope:
        queryset = queryset.filter(Q(label_scope__contains=[label_scope]) | Q(label_scope__contains=["common"]))

    if "parent_id" in params:
        queryset = queryset.filter(parent_id=params["parent_id"])

    if "name" in params:
        queryset = queryset.filter(name__icontains=params["name"])

    if "is_default" in params:
        queryset = queryset.filter(is_default=params["is_default"])

    # If parent_id is not provided, return root labels (compatible with LabelFilter.filter_queryset)
    if "parent_id" not in params:
        root_label_ids = []
        for label in queryset:
            if label.parent_id is None:
                root_label_ids.append(label.id)
            else:
                root_label_ids.append(label.parent_id)
        queryset = Label.objects.filter(id__in=root_label_ids)

    child_subquery = Label.objects.filter(parent_id=OuterRef("pk"))
    queryset = queryset.annotate(has_children=Exists(child_subquery)).order_by(order_by)

    labels, count = paginate_list_data(request, queryset)
    data = LabelSerializer(labels, many=True).data

    return {
        "result": True,
        "data": data,
        "count": count,
        "code": err_code.SUCCESS.code,
    }
