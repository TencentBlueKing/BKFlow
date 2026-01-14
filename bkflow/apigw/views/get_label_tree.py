"""APIGW: label tree."""

from apigw_manager.apigw.decorators import apigw_require
from blueapps.account.decorators import login_exempt
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from bkflow.apigw.decorators import check_jwt_and_space, return_json_response
from bkflow.apigw.serializers.label import LabelTreeFilterSerializer
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.label.models import Label, TemplateLabelRelation
from bkflow.label.serializers import LabelSerializer
from bkflow.utils import err_code


def _parse_ids_csv(value):
    if not value:
        return []
    return [int(x) for x in str(value).split(",") if str(x).strip()]


def _get_task_label_ids(space_id, task_ids):
    """Fetch label ids for tasks from TASK module via task_list(id=...)."""
    if not task_ids:
        return set()

    client = TaskComponentClient(space_id=space_id)
    label_ids = set()

    for task_id in task_ids:
        result = client.task_list(data={"space_id": space_id, "id": task_id, "limit": 1, "offset": 0})
        if not result.get("result"):
            return result

        data = result.get("data") or {}
        results = data.get("results") or []
        if not results:
            continue
        task = results[0]
        for lid in task.get("labels") or []:
            try:
                label_ids.add(int(lid))
            except Exception:
                continue

    return label_ids


def _expand_with_ancestors(space_id, label_ids):
    """Expand label_ids with all ancestor labels (parents up to root)."""
    if not label_ids:
        return set()

    all_ids = set(label_ids)
    frontier = set(label_ids)

    # iterative parent walk to avoid N+1
    while frontier:
        parents = (
            Label.objects.filter(id__in=frontier, space_id__in=[-1, int(space_id)])
            .exclude(parent_id__isnull=True)
            .values_list("parent_id", flat=True)
        )
        parent_set = {pid for pid in parents if pid is not None}
        new_parents = parent_set - all_ids
        if not new_parents:
            break
        all_ids |= new_parents
        frontier = new_parents

    return all_ids


def _build_tree(labels):
    """Build a tree from flat label list."""
    nodes = {item["id"]: item for item in labels}
    for item in nodes.values():
        item["children"] = []

    roots = []
    for item in nodes.values():
        pid = item.get("parent_id")
        if pid and pid in nodes:
            nodes[pid]["children"].append(item)
        else:
            roots.append(item)

    # sort by name for stable output
    def sort_children(node):
        node["children"].sort(key=lambda x: x.get("name") or "")
        node["has_children"] = bool(node["children"])
        for c in node["children"]:
            sort_children(c)

    roots.sort(key=lambda x: x.get("name") or "")
    for r in roots:
        sort_children(r)

    return roots


def _paginate_roots(request, roots, offset=None, limit=None):
    """Paginate root nodes only to keep subtrees intact."""
    # Backward compatible: only paginate when client explicitly passes offset/limit
    if offset is None and limit is None:
        return roots, len(roots)

    try:
        offset = 0 if offset is None else int(offset)
        limit = 100 if limit is None else int(limit)
    except Exception:
        offset, limit = 0, 100

    if offset < 0 or limit < 0:
        offset, limit = 0, 100

    # keep same cap as paginate_list_data
    limit = 200 if limit > 200 else limit

    count = len(roots)
    return roots[offset : offset + limit], count


@login_exempt
@csrf_exempt
@require_GET
@apigw_require
@check_jwt_and_space
@return_json_response
def get_label_tree(request, space_id):
    ser = LabelTreeFilterSerializer(data=request.GET)
    ser.is_valid(raise_exception=True)

    label_scope = ser.validated_data.get("label_scope")
    task_ids = _parse_ids_csv(ser.validated_data.get("task_ids"))
    template_ids = _parse_ids_csv(ser.validated_data.get("template_ids"))

    offset = ser.validated_data.get("offset")
    limit = ser.validated_data.get("limit")

    base_queryset = Label.objects.filter(space_id__in=[-1, int(space_id)])
    if label_scope:
        base_queryset = base_queryset.filter(
            Q(label_scope__contains=[label_scope]) | Q(label_scope__contains=["common"])
        )

    # no filter -> full tree in this scope
    if not task_ids and not template_ids:
        all_labels = list(base_queryset.order_by("name"))
        data = LabelSerializer(all_labels, many=True).data
        roots = _build_tree(list(data))
        paged, count = _paginate_roots(request, roots, offset=offset, limit=limit)
        return {
            "result": True,
            "data": paged,
            "count": count,
            "code": err_code.SUCCESS.code,
        }

    # collect referenced label ids
    label_ids = set()
    if template_ids:
        label_ids |= set(
            TemplateLabelRelation.objects.filter(template_id__in=template_ids).values_list("label_id", flat=True)
        )

    task_label_ids = _get_task_label_ids(int(space_id), task_ids)
    if isinstance(task_label_ids, dict):
        # propagate task module error
        return task_label_ids
    label_ids |= set(task_label_ids)

    if not label_ids:
        return {
            "result": True,
            "data": [],
            "count": 0,
            "code": err_code.SUCCESS.code,
        }

    include_ids = _expand_with_ancestors(space_id, label_ids)

    labels = list(base_queryset.filter(id__in=include_ids).order_by("name"))
    data = LabelSerializer(labels, many=True).data
    roots = _build_tree(list(data))
    paged, count = _paginate_roots(request, roots, offset=offset, limit=limit)
    return {
        "result": True,
        "data": paged,
        "count": count,
        "code": err_code.SUCCESS.code,
    }
