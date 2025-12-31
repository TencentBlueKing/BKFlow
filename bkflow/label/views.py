import django_filters
from django.db.models import Count, Exists, OuterRef, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.label.models import TemplateLabelRelation
from bkflow.utils.mixins import BKFLOWNoMaxLimitPagination
from bkflow.utils.views import AdminModelViewSet

from .models import Label
from .serializers import LabelRefSerializer, LabelSerializer


class LabelFilter(django_filters.FilterSet):
    """标签过滤集：指定必须过滤字段"""

    space_id = django_filters.NumberFilter(required=True, method="filter_space_id")
    label_scope = django_filters.CharFilter(method="filter_label_scope")
    parent_id = django_filters.NumberFilter(method="filter_parent_id")
    name = django_filters.CharFilter(method="filter_name")
    is_default = django_filters.BooleanFilter(method="filter_is_default")

    class Meta:
        model = Label
        fields = ["space_id", "label_scope", "parent_id", "name", "is_default"]

    def filter_space_id(self, queryset, name, value):
        return queryset.filter(space_id__in=[-1, value])

    def filter_label_scope(self, queryset, name, value):
        return queryset.filter(Q(label_scope__contains=[value]) | Q(label_scope__contains=["common"]))

    def filter_parent_id(self, queryset, name, value):
        return queryset.filter(parent_id=value)

    def filter_name(self, queryset, name, value):
        return queryset.filter(name__icontains=value)

    def filter_is_default(self, queryset, name, value):
        return queryset.filter(is_default=value)

    def filter_queryset(self, queryset):
        """
        重写父类方法，处理默认值逻辑 + 搜索兼容
        """
        queryset = super().filter_queryset(queryset)

        params = self.data

        has_parent_id = "parent_id" in params


        if not has_parent_id:
            # 过滤出根标签
            root_label_ids = []
            for label in queryset:
                if label.parent_id is None:
                    root_label_ids.append(label.id)
                else:
                    root_label_ids.append(label.parent_id)
            return self.Meta.model.objects.filter(id__in=root_label_ids)

        return queryset


class LabelViewSet(AdminModelViewSet):
    """
    标签管理 ViewSet
    """
    swagger_tags = ["label"]
    queryset = Label.objects.all().order_by("-updated_at")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]
    serializer_class = LabelSerializer
    pagination_class = BKFLOWNoMaxLimitPagination

    def get_filterset_class(self):
        if self.action in ["list", "retrieve"]:
            return LabelFilter
        return None

    def get_queryset(self):
        queryset = super().get_queryset()
        child_subquery = Label.objects.filter(parent_id=OuterRef("pk"))

        filterset_class = self.get_filterset_class()
        if filterset_class:
            filterset = filterset_class(self.request.query_params, queryset=queryset, request=self.request)
            if not filterset.is_valid():
                return queryset.none()
            queryset = filterset.qs

        queryset = queryset.annotate(has_children=Exists(child_subquery))
        return queryset

    def create(self, request, *args, **kwargs):
        """
        覆盖 create 方法：
        1. 如果 name 是 '一级/二级' 格式，则查找或自动创建 '一级' 标签。
        2. 将 '二级' 标签关联到其父级 ID 下。
        """
        data = request.data.copy()
        name_parts = data.get("name", "").split("/")

        if len(name_parts) == 2:
            parent_name = name_parts[0].strip()  # 一级标签名称
            child_name = name_parts[1].strip()  # 二级标签名称

            parent_label_pk = None

            try:
                # 尝试查找已存在的父标签 (一级标签，parent_id为空)
                parent_label = Label.objects.get(name=parent_name, parent_id__isnull=True)
                parent_label_pk = parent_label.pk
            except Label.DoesNotExist:
                # 如果一级标签不存在，则自动创建
                data["name"] = parent_name
                parent_serializer = self.get_serializer(data=data)
                # 校验并保存一级标签
                parent_serializer.is_valid(raise_exception=True)
                parent_instance = parent_serializer.save()
                parent_label_pk = parent_instance.pk

            # 填充 parent_id 并修正 name 字段 (用于创建二级标签)
            data["parent_id"] = parent_label_pk
            data["name"] = child_name

        # 创建一级/二级标签
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        """删除标签，级联删除子标签"""
        instance = self.get_object()

        # 如果是一级标签，删除所有子标签
        if instance.parent_id is None:
            Label.objects.filter(parent_id=instance.pk).delete()

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], serializer_class=LabelRefSerializer)
    def get_label_ref_count(self, request, *args, **kwargs):
        """获取标签引用数量"""
        ser = LabelRefSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        validated_params = ser.validated_data
        label_ids = validated_params["label_ids"].split(",")

        # 调用任务组件接口获取任务引用数量
        client = TaskComponentClient(space_id=validated_params["space_id"])
        result = client.get_task_label_ref_count(validated_params["space_id"], validated_params["label_ids"])
        if not result["result"]:
            return Response(result)
        label_task_ref_count_map = result["data"]

        # 获取模板引用数量
        aggregation_qs = (
            TemplateLabelRelation.objects.filter(label_id__in=label_ids).values("label_id").annotate(count=Count("id"))
        )
        label_template_count_map = {item["label_id"]: item["count"] for item in aggregation_qs}

        # 合并结果
        ref_result = {}
        for label_id in label_ids:
            ref_result[label_id] = {
                "template_count": label_template_count_map.get(int(label_id), 0),
                "task_count": label_task_ref_count_map.get(label_id, 0),
            }

        return Response(ref_result)
