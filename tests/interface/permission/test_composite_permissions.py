"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db.models.query import QuerySet
from django.test import override_settings
from django.utils import timezone

from bkflow.admin.models import ModuleInfo
from bkflow.contrib.api.collections.task import TaskComponentClient
from bkflow.decision_table.permissions import DecisionTableUserPermission
from bkflow.exceptions import APIRequestError, ValidationError
from bkflow.interface.task.permissions import ScopePermission as TaskScopePermission
from bkflow.interface.task.permissions import (
    TaskMockTokenPermission,
    TaskTokenPermission,
)
from bkflow.interface.task.view import TaskInterfaceViewSet
from bkflow.permission.grants import Grant
from bkflow.permission.models import Token
from bkflow.permission.services import issue_token, revoke_tokens
from bkflow.pipeline_plugins.query.uniform_api.utils import check_resource_token
from bkflow.plugin.permissions import PluginTokenPermissions
from bkflow.template.models import Template, TemplateSnapshot
from bkflow.template.permissions import ScopePermission as TemplateScopePermission
from bkflow.template.permissions import (
    TemplateMockPermission,
    TemplateRelatedResourcePermission,
)
from bkflow.template.serializers.template import TemplateSerializer

pytestmark = pytest.mark.django_db
GRANTS = (Grant("TEMPLATE", "100", "MOCK"), Grant("TASK", "200", "OPERATE"))


def issue(grants=GRANTS, user="alice", space_id=1):
    """真实签发，不替换验证或数据库逻辑。"""
    return issue_token(space_id, user, grants, 3600, False)


def request_for(token, user="alice", space_id=1, **params):
    """模拟已认证请求上下文，使用真实票据值。"""
    return SimpleNamespace(
        token=token.pk,
        user=SimpleNamespace(username=user, is_superuser=False),
        query_params={"space_id": space_id, **params},
        data={},
        method="GET",
    )


def view_for(action="get_task_detail", task_id=200):
    """复用真实 ViewSet 动作分组。"""
    return SimpleNamespace(
        action=action,
        kwargs={"task_id": task_id},
        MOCK_ABOVE_ACTIONS=TaskInterfaceViewSet.MOCK_ABOVE_ACTIONS,
        OPERATE_ABOVE_ACTIONS=TaskInterfaceViewSet.OPERATE_ABOVE_ACTIONS,
        EDIT_ABOVE_ACTIONS=["update"],
    )


@pytest.fixture
def template():
    """真实模板与 task 100 共享 ID，但属于不同 scope。"""
    snapshot = TemplateSnapshot.objects.create(data={}, md5sum="test")
    Template.objects.bulk_create(
        [Template(id=100, space_id=1, snapshot_id=snapshot.id, name="test", scope_type="biz", scope_value="a")]
    )
    return Template.objects.get(pk=100)


@pytest.fixture
def engine():
    """引擎边界按任务 ID 返回具体父子关系、scope 与创建方式。"""
    ModuleInfo.objects.create(type="TASK", space_id=0, url="http://engine.invalid", token="test")
    tasks = {
        "100": {"scope_type": "biz", "scope_value": "b", "template_id": 100},
        "200": {"scope_type": "biz", "scope_value": "a", "template_id": 100, "create_method": "API"},
        "201": {"parent_task_info": {"task_id": 200}, "template_id": 100, "create_method": "MOCK"},
        "202": {"parent_task_info": {"task_id": 201}},
        "300": {"parent_task_info": {"task_id": 301}},
        "301": {"parent_task_info": {"task_id": 300}},
        "400": {"parent_task_info": {"task_id": 400}},
        "500": {"create_method": "MOCK", "template_id": 999},
    }

    def detail(task_id):
        if str(task_id) == "600":
            raise APIRequestError("engine unavailable")
        data = tasks.get(str(task_id))
        return {"result": data is not None, "data": data}

    with patch.object(TaskComponentClient, "get_task_detail", side_effect=detail) as mocked:
        yield mocked


def test_complete_grant_permission_matrix_and_request_cache(template, django_assert_num_queries):
    """同一票据分别授权模板与任务，不能把动作与资源交叉拼接。"""
    token = issue()
    request = request_for(token)
    assert TemplateMockPermission().has_object_permission(request, view_for(), template)
    with django_assert_num_queries(0):
        assert TaskTokenPermission().has_permission(request, view_for("operate_task"))
    assert Token.verify(1, "alice", "TEMPLATE", "100", "MOCK", token.pk)
    assert Token.verify(1, "alice", "TASK", "200", "OPERATE", token.pk)
    assert not Token.verify(1, "alice", "TEMPLATE", "100", "OPERATE", token.pk)
    assert not Token.verify(1, "alice", "TASK", "200", "MOCK", token.pk)
    assert not TaskTokenPermission().has_permission(request, view_for("get_task_mock_data"))


@pytest.mark.parametrize("composite", [False, True])
def test_scope_same_numeric_id_uses_actual_target(template, engine, composite):
    """所有 HTTP scope 路径必须区分同 ID 的模板与任务。"""
    grants = [Grant("SCOPE", "biz_a", "MOCK")]
    if composite:
        grants.append(Grant("TASK", "999", "VIEW"))
    request = request_for(issue(grants))
    assert TemplateScopePermission().has_object_permission(request, view_for(), template)
    assert not TaskScopePermission().has_permission(request, view_for(task_id=100))
    assert TaskScopePermission().has_permission(request, view_for(task_id=200))
    assert TemplateRelatedResourcePermission().has_permission(
        request_for(issue(grants), template_id=100), view_for("list")
    )


def test_composite_scope_requires_target_legacy_fallback_remains(template, engine):
    """只有旧内部 scope 调用保留模板优先回退。"""
    old = issue([Grant("SCOPE", "biz_a", "VIEW")])
    combo = issue([Grant("SCOPE", "biz_a", "VIEW"), Grant("TASK", "999", "VIEW")])
    assert Token.verify(1, "alice", "SCOPE", 100, "VIEW", old.pk)
    assert not Token.verify(1, "alice", "SCOPE", 100, "VIEW", combo.pk)
    assert not Token.verify(1, "alice", "SCOPE", "biz_a", "VIEW", combo.pk)
    assert Token.verify(1, "alice", "SCOPE", 100, "VIEW", combo.pk, target_resource_type="TEMPLATE")
    assert not Token.verify(1, "alice", "SCOPE", 100, "VIEW", combo.pk, target_resource_type="TASK")


@pytest.mark.parametrize(
    "target,allowed",
    [(200, True), (201, True), (202, True), (100, False), (300, False), (400, False), (600, False), (999, False)],
)
def test_task_descendants_cycles_and_failure(engine, target, allowed):
    """父任务授权仅向后代传播，循环与引擎失败有限终止。"""
    assert Token.verify(1, "alice", "TASK", target, "OPERATE", issue().pk) is allowed
    assert engine.call_count <= 3


def test_child_does_not_authorize_parent(engine):
    """子任务不能反向授权父任务。"""
    token = issue([Grant("TASK", "201", "VIEW")])
    assert not Token.verify(1, "alice", "TASK", 200, "VIEW", token.pk)


@pytest.mark.parametrize("task_id,allowed", [(201, True), (200, False), (500, False), (600, False), (999, False)])
def test_template_mock_only_own_mock_tasks(engine, task_id, allowed):
    """模板 MOCK 只允许本模板创建的 MOCK 任务。"""
    assert TaskMockTokenPermission().has_permission(request_for(issue()), view_for(task_id=task_id)) is allowed


@pytest.mark.parametrize("case", ["wrong_user", "wrong_space", "expired", "corrupt"])
def test_invalid_whole_token_rejected_by_every_consumer(template, engine, case):
    """用户、空间、到期及任一明细损坏影响所有消费入口。"""
    token = issue()
    user, space_id = "alice", 1
    if case == "wrong_user":
        user = "bob"
    elif case == "wrong_space":
        space_id = 2
    elif case == "expired":
        Token.objects.filter(pk=token.pk).update(expired_time=timezone.now())
    else:
        token.grants.filter(resource_type="TASK").update(grant_hash="bad")
    request = request_for(token, user, space_id, template_id=100)
    assert not Token.verify(space_id, user, "TEMPLATE", 100, "MOCK", token.pk)
    assert not TaskTokenPermission().has_permission(request, view_for("operate_task"))
    assert not PluginTokenPermissions().has_permission(request, view_for())
    assert not DecisionTableUserPermission().has_permission(request, view_for("list"))
    assert not DecisionTableUserPermission().has_object_permission(
        request, view_for("retrieve"), SimpleNamespace(template_id=100)
    )
    with pytest.raises(ValidationError):
        check_resource_token(lambda *args, **kwargs: True)(request, space_id=space_id)
    with pytest.raises(APIRequestError):
        TaskInterfaceViewSet().get_space_id(request)


def test_composite_old_fields_never_add_authority(template):
    """组合主表残留旧字段不能增加任何授权。"""
    token = issue()
    Token.objects.filter(pk=token.pk).update(resource_type="TASK", resource_id="300", permission_type="MOCK")
    assert not Token.verify(1, "alice", "TASK", 300, "MOCK", token.pk)
    assert not Token.objects.get_resource_tokens(token.pk, {"task_id": 300}, user="alice", space_id=1).exists()


@pytest.mark.parametrize(
    "grants,action,allowed",
    [
        ([Grant("TEMPLATE", "100", "VIEW")], "list", False),
        ([Grant("TEMPLATE", "100", "MOCK")], "list", True),
        ([Grant("TEMPLATE", "100", "EDIT")], "update", True),
        ([Grant("TEMPLATE", "00100", "EDIT")], "update", True),
        ([Grant("TASK", "600", "VIEW")], "retrieve", False),
        ([Grant("TASK", "200", "OPERATE")], "retrieve", True),
        ([Grant("TASK", "200", "OPERATE")], "update", False),
        ([Grant("TASK", "500", "VIEW")], "retrieve", False),
        ([Grant("SCOPE", "biz_a", "MOCK")], "list", False),
    ],
)
def test_decision_table_preserves_resource_action_rules(template, engine, grants, action, allowed):
    """决策表保留原有模板编辑与任务只读关联规则。"""
    token = issue([*grants, Grant("TASK", "999", "VIEW")])
    permission = DecisionTableUserPermission()
    request = request_for(token, template_id=100)
    assert bool(permission.has_permission(request, view_for(action))) is allowed
    assert not permission.has_object_permission(request, view_for(action), SimpleNamespace(template_id=999))


@pytest.mark.parametrize(
    "params,allowed",
    [
        ({"template_id": 100}, True),
        ({"task_id": 200}, True),
        ({"scope_type": "biz", "scope_value": "a"}, False),
        ({"template_id": 999, "task_id": 200}, False),
        ({"template_id": None, "task_id": 200}, False),
        ({"template_id": 100, "task_id": 999}, True),
        ({}, True),
    ],
)
def test_uniform_api_resource_precedence_and_queryset(params, allowed):
    """保留模板字段存在优先及无筛选时的旧资源规则，返回去重 QuerySet。"""
    token = issue()
    queryset = Token.objects.get_resource_tokens(token.pk, params, user="alice", space_id=1)
    assert isinstance(queryset, QuerySet)
    assert queryset.exists() is allowed
    assert queryset.count() == int(allowed)
    request = request_for(token, **params)
    if allowed:
        assert check_resource_token(lambda *args, **kwargs: "ok")(request, space_id=1) == "ok"
    else:
        with pytest.raises(ValidationError):
            check_resource_token(lambda *args, **kwargs: "ok")(request, space_id=1)


def test_uniform_api_scope_or_template_matches_once():
    """scope 与模板或多条动作同时命中，主票据只返回一次。"""
    token = issue([Grant("SCOPE", "biz_a", "VIEW"), Grant("TEMPLATE", "100", "MOCK"), Grant("TEMPLATE", "100", "EDIT")])
    params = {"scope_type": "biz", "scope_value": "a", "template_id": 100}
    assert Token.objects.get_resource_tokens(token.pk, params, user="alice", space_id=1).count() == 1


def test_auth_aggregates_valid_grants_legacy_fallback_and_admin_arrays(template):
    """混合票据去重，完整性失败整票据排除，历史 FLOW_OPERATE 和管理员数组不变。"""
    token = issue()
    issue([Grant("TEMPLATE", "100", "MOCK")])
    issue([Grant("TEMPLATE", "100", "OPERATE")])
    issue([Grant("SCOPE", "biz_a", "EDIT")])
    issue([Grant("TEMPLATE", "100", "VIEW")], user="bob")
    issue([Grant("TEMPLATE", "100", "VIEW")], space_id=2)
    expired = issue([Grant("TASK", "200", "VIEW")])
    Token.objects.filter(pk=expired.pk).update(expired_time=timezone.now())
    broken = issue([Grant("TEMPLATE", "100", "VIEW"), Grant("TASK", "200", "MOCK")])
    broken.grants.filter(resource_type="TASK").delete()
    request = request_for(token)
    serializer = TemplateSerializer(context={"request": request})
    assert set(serializer.get_current_user_auth(template)) == {"MOCK", "OPERATE", "EDIT"}
    data = {
        "result": True,
        "data": {"id": 200, "template_id": 100, "space_id": 1, "scope_type": "biz", "scope_value": "a"},
    }
    TaskInterfaceViewSet._inject_user_task_auth(request, data)
    assert set(data["data"]["auth"]) == {"OPERATE", "FLOW_MOCK", "FLOW_OPERATE", "EDIT"}
    assert len(data["data"]["auth"]) == 4
    request.user.is_superuser = True
    with override_settings(BLOCK_ADMIN_PERMISSION=False):
        assert serializer.get_current_user_auth(template) == ["VIEW", "EDIT", "MOCK"]
    TaskInterfaceViewSet._inject_user_task_auth(request, data)
    assert data["data"]["auth"] == ["VIEW", "OPERATE", "FLOW_VIEW", "FLOW_EDIT", "FLOW_MOCK"]


def test_disabling_issue_flag_does_not_disable_consumption_and_revoke_is_whole(template):
    """关闭申请后已发票据继续可用，命中一项撤销后两个入口均拒绝。"""
    token = issue()
    with override_settings(TOKEN_COMPOSITE_ENABLED=False):
        assert TemplateMockPermission().has_object_permission(request_for(token), view_for(), template)
        assert TaskTokenPermission().has_permission(request_for(token), view_for("operate_task"))
        assert revoke_tokens(1, {"resource_type": "TEMPLATE", "resource_id": "100"}) == 1
        assert not TemplateMockPermission().has_object_permission(request_for(token), view_for(), template)
        assert not TaskTokenPermission().has_permission(request_for(token), view_for("operate_task"))


def test_admin_grants_inline_cannot_append_modify_or_delete():
    """管理展示不提供对已签发授权集合的增删改入口。"""
    from django.contrib.admin.sites import AdminSite

    from bkflow.permission.admin import TokenAdmin

    inline_class = TokenAdmin.inlines[0]
    inline = inline_class(Token, AdminSite())
    request = request_for(issue())
    assert inline.has_add_permission(request) is False
    assert inline.has_change_permission(request) is False
    assert inline.has_delete_permission(request) is False
    assert set(inline.readonly_fields) >= {"resource_type", "resource_id", "permission_type", "grant_hash"}


@pytest.mark.parametrize("composite", [False, True])
@pytest.mark.parametrize("case", ["wrong_user", "wrong_space", "expired"])
def test_auxiliary_invalid_tokens_independently(composite, case):
    """单项与组合辅助路径独立证明错用户、空间与过期均拒绝。"""
    token = issue(GRANTS if composite else GRANTS[:1])
    user, space_id = "alice", 1
    if case == "wrong_user":
        user = "bob"
    elif case == "wrong_space":
        space_id = 2
    else:
        Token.objects.filter(pk=token.pk).update(expired_time=timezone.now())
    request = request_for(token, user, space_id, template_id=100)
    assert not PluginTokenPermissions().has_permission(request, view_for())
    assert not DecisionTableUserPermission().has_permission(request, view_for("list"))
    assert not Token.objects.get_resource_tokens(token.pk, {"template_id": 100}, user=user, space_id=space_id).exists()
    with pytest.raises(ValidationError):
        check_resource_token(lambda *args, **kwargs: True)(request, space_id=space_id)


def test_auth_ignores_main_field_leaks_and_batches_queries(template, django_assert_num_queries):
    """多个完整票据一次主表一次明细查询，旧字段与游离明细不贡献权限。"""
    from bkflow.permission.grants import grant_hash
    from bkflow.permission.models import TokenGrant
    from bkflow.permission.services import iter_user_grants

    token = issue()
    Token.objects.filter(pk=token.pk).update(resource_type="TASK", resource_id="999", permission_type="MOCK")
    old = issue([Grant("TEMPLATE", "100", "VIEW")])
    stray = Grant("TASK", "999", "EDIT")
    TokenGrant.objects.create(token=old, **stray.as_dict(), grant_hash=grant_hash(stray))
    with django_assert_num_queries(2):
        grants = list(iter_user_grants(1, "alice", [("TEMPLATE", 100), ("TASK", 999)]))
    assert set(grants) == {Grant("TEMPLATE", "100", "MOCK"), Grant("TEMPLATE", "100", "VIEW")}


def test_scope_failure_and_unknown_target_rejected(template, engine):
    """scope 的外部读取失败、目标不存在及未知目标类型都拒绝。"""
    token = issue([Grant("SCOPE", "biz_a", "VIEW"), Grant("TASK", "999", "VIEW")])
    for target_type, target_id in [("TASK", 600), ("TASK", 999), ("TEMPLATE", 999), ("LABEL", 100)]:
        assert not Token.verify(1, "alice", "SCOPE", target_id, "VIEW", token.pk, target_resource_type=target_type)
