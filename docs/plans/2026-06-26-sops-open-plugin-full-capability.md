# 标准运维全量插件能力接入 BKFlow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `2026-04-20` 集成基础上，向后兼容地扩展 `uniform_api v4.0.0` execute 协议透传业务 `context`，并新增「平台级来源准入 + 空间级 per-plugin」两层准入与四处服务端强校验，使选定的「有业务含义的空间」可使用标准运维全部插件。

**Architecture:** 运行时 `uniform_api v4.0.0` 组件在 execute payload 上附加可选 `context`（scope/operator/space/task/node，全部取自运行时已有数据）；新增 `OpenPluginSpaceGrant` 作为平台级第 1 层闸门，复用 `SpaceOpenPluginAvailability` 作为空间级第 2 层；在查询/目录/模板保存/任务创建/任务启动处统一校验 grant + enabled + available + 不在黑名单。BKFlow 不解析 sops `project`，只透传 scope，解析在标准运维侧。

**Tech Stack:** Django, DRF, Celery, `uniform_api` wrapper（pipeline component framework）, BKFlow APIGW, pytest

**Spec:** `docs/specs/2026-06-26-sops-open-plugin-full-capability-design.md`（前序集成设计 `docs/specs/2026-04-20-sops-open-plugin-integration-design.md`）

**配套：** 标准运维侧计划见 bk-sops 仓库 `docs/plans/2026-06-26-plugin-gateway-full-capability.md`

**Commit 约定：** `<type>(<scope>): <subject> --story=133649781`（见 `.ai/rules/git-commit-convention.mdc`，本特性沿用 story `133649781`）

---

## 关键约束（执行者必读）

1. **不升 wrapper 版本**：仅在 execute body 增加可选 `context`，`detail_meta` / polling / callback 协议不变。老来源（v2/v3/v4 不带 context）必须仍可用。
2. **不在 BKFlow 解析 project**：`context` 只透传 `scope_type/scope_value/operator/...`，sops project 解析在标准运维侧。
3. **两层准入**：第 1 层 `OpenPluginSpaceGrant`（平台授权空间可接入某 `source_key`），第 2 层 `SpaceOpenPluginAvailability`（空间内 per-plugin 开关）。未准入空间**连该来源目录都看不到**。
4. **强校验不只前端**：查询、模板保存、任务创建、任务启动四处都要服务端校验。
5. **context 字段全部取自运行时已有数据**（`_load_parent_data` / `parent_data`），不需要用户在表单填写。
6. **TDD**：每个 Task 先写失败测试。测试用 `pytest`（`DJANGO_SETTINGS_MODULE=settings`，见 `pytest.ini`）。
7. **APIGW 改动**：任何 `bkflow/apigw/` 改动按 `.ai/rules/apigw-resource-sync.mdc` 同步 `api-resources.yml` + docs zip（`bash scripts/apigw_docs.sh`）。

---

## File Structure

| 文件 | 操作 | 责任 |
|------|------|------|
| `bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py` | Modify | `build_open_plugin_execute_payload` 增可选 `context`；execute 分支构造并透传 `context` |
| `bkflow/plugin/models.py` | Modify | 新增 `OpenPluginSpaceGrant` 模型 |
| `bkflow/plugin/migrations/0004_open_plugin_space_grant.py` | Create | 模型迁移 |
| `bkflow/plugin/migrations/0005_backfill_open_plugin_grant.py` | Create | 存量已配置 sops 来源的空间默认授 grant 的数据迁移 |
| `bkflow/plugin/admin.py` | Modify | 注册 `OpenPluginSpaceGrant` admin |
| `bkflow/plugin/services/open_plugin_grant.py` | Create | `OpenPluginGrantService`：grant 判定、授予/撤销、按来源过滤 |
| `bkflow/plugin/management/commands/grant_open_plugin_source.py` | Create | 平台管理员批量授予/撤销空间来源准入 |
| `bkflow/plugin/services/open_plugin_catalog.py` | Modify | `list_space_plugins` / `enable_all_visible_plugins` 受 grant 约束；按 grant 过滤来源 |
| `bkflow/plugin/services/plugin_schema_service.py` | Modify | `_list_uniform_api_plugins_from_catalog` 接入 grant 守卫 |
| `bkflow/plugin/services/open_plugin_snapshot.py` | Modify | `validate_pipeline_tree` 增加 grant 守卫（统一校验入口） |
| `bkflow/apigw/views/list_plugins.py` | Modify | 查询接口接入 grant 校验 |
| `bkflow/apigw/views/get_plugin_schema.py` | Modify | schema 接口接入 grant 校验 |
| `bkflow/apigw/views/create_task.py` | Modify | 创建任务校验（复用 `validate_pipeline_tree`） |
| `bkflow/apigw/views/operate_task.py` | Modify | 启动任务校验 |
| `bkflow/task/views.py` / `bkflow/task/operations.py` | Modify | 内部 REST 创建/启动任务补开放插件校验 |
| `bkflow/template/serializers/template.py` | Modify | 模板保存校验已走 `validate_pipeline_tree`（确认 grant 守卫生效） |
| `bkflow/space/views.py` / `serializers.py` / `urls.py` | Modify | 空间管理接口在 grant 约束下治理 per-plugin |
| `bkflow/apigw/management/commands/data/api-resources.yml` | Modify | 如有接口签名变化同步 |
| `bkflow/apigw/docs/zh/*.md` / `bkflow/apigw/docs/apigw-docs.zip` | Modify | 文档与归档同步 |
| `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py` | Modify | `context` 透传 + 兼容回归 |
| `tests/interface/plugin/services/test_open_plugin_grant.py` | Create | grant 服务测试 |
| `tests/interface/plugin/services/test_open_plugin_catalog.py` | Modify | grant 约束下目录可见性 |
| `tests/interface/plugin/services/test_open_plugin_snapshot.py` | Modify | grant 守卫校验 |
| `tests/interface/apigw/test_list_plugins.py` / `test_get_plugin_schema.py` / `test_create_task.py` / `test_operate_task.py` | Modify | 四处强校验 |
| `tests/interface/space/test_space_views.py` | Modify | 一键全开仅在已准入空间生效 |

**Files NOT changed:** `uniform_api/v1_0_0.py` / `v2_0_0.py` / `v3_0_0.py`（仅复用 `_load_parent_data`）；引擎与快照体系。

---

### Task 1: 协议扩展——execute payload 透传 `context`

**Files:**
- Modify: `bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py`
- Test: `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py`

- [ ] **Step 1: 写失败测试**

在 `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py` 追加：

```python
from bkflow.pipeline_plugins.components.collections.uniform_api.v4_0_0 import (
    build_open_plugin_execute_payload,
)


def test_build_payload_with_context():
    payload = build_open_plugin_execute_payload(
        source_key="sops", plugin_id="builtin__job_execute_task", plugin_version="legacy",
        inputs={"a": 1}, client_request_id="r1", callback_url="https://cb", callback_token="tok",
        context={"scope_type": "biz", "scope_value": "2", "operator": "zhangsan", "space_id": 10},
    )
    assert payload["context"]["scope_type"] == "biz"
    assert payload["context"]["operator"] == "zhangsan"
    assert payload["inputs"] == {"a": 1}


def test_build_payload_without_context_is_backward_compatible():
    payload = build_open_plugin_execute_payload(
        source_key="sops", plugin_id="x", plugin_version="v", inputs={}, client_request_id="r2",
        callback_url="https://cb", callback_token="tok",
    )
    assert "context" not in payload  # 不传 context → 老行为，标准运维侧按 default_project_id 兜底
```

并补一个组件级测试：执行开放插件分支时，POST 给标准运维的 body 含 `context`（mock `requests`/`http` 客户端，断言 `json=` 里有 `context.scope_type`）。复用文件内已有的执行分支测试夹具，仅追加对 `context` 字段的断言。

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`
Expected: FAIL，`build_open_plugin_execute_payload` 不接受 `context` 参数 / payload 无 `context`

- [ ] **Step 3: 扩展 `build_open_plugin_execute_payload`**

`bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py`（在现有签名末尾追加可选 `context`）：

```python
def build_open_plugin_execute_payload(
    source_key,
    plugin_id,
    plugin_version,
    inputs,
    client_request_id,
    callback_url,
    callback_token,
    project_id=None,
    context=None,
):
    payload = {
        "source_key": source_key,
        "plugin_id": plugin_id,
        "plugin_version": plugin_version,
        "client_request_id": client_request_id,
        "callback_url": callback_url,
        "callback_token": callback_token,
        "inputs": inputs,
    }
    if project_id:
        payload["project_id"] = project_id
    if context:
        payload["context"] = context
    return payload
```

- [ ] **Step 4: 在 execute 分支构造并透传 `context`**

在 `_dispatch_schedule_trigger` 的开放插件分支（当前构造 `execute_payload` 处，约 L200-208）。`context` 全部取自运行时已有数据（`_load_parent_data` 返回的 `extra_data` + `parent_data`）：

```python
        operator, space_id, extra_data = self._load_parent_data(parent_data)
        open_plugin_context = {
            "scope_type": extra_data.get("scope_type"),
            "scope_value": extra_data.get("scope_value"),
            "operator": operator,
            "space_id": space_id,
            "task_id": extra_data.get("task_id"),
            "node_id": extra_data.get("node_id") or self.id,
            "task_name": extra_data.get("task_name"),
        }
        execute_payload = build_open_plugin_execute_payload(
            source_key=source_key,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            inputs=api_data,
            client_request_id=client_request_id,
            callback_url=callback_url,
            callback_token=callback_token,
            context=open_plugin_context,
        )
```

> 若 `_load_parent_data` 已在分支前调用过，复用其返回值，避免重复调用。`node_id` 缺省用 `self.id`。

- [ ] **Step 5: 运行测试至通过**

Run: `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`
Expected: PASS，且 v1/v2/v3 既有测试不受影响

- [ ] **Step 6: Commit**

```bash
git add bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py \
  tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py
git commit -m "feat(uniform_api): execute 协议向后兼容透传业务 context --story=133649781"
```

---

### Task 2: 第 1 层来源准入——`OpenPluginSpaceGrant` 模型 + 服务 + 管理

**Files:**
- Modify: `bkflow/plugin/models.py`
- Create: `bkflow/plugin/migrations/0004_open_plugin_space_grant.py`
- Create: `bkflow/plugin/services/open_plugin_grant.py`
- Modify: `bkflow/plugin/admin.py`
- Create: `bkflow/plugin/management/commands/grant_open_plugin_source.py`
- Test: `tests/interface/plugin/services/test_open_plugin_grant.py`

- [ ] **Step 1: 写 grant 服务失败测试**

`tests/interface/plugin/services/test_open_plugin_grant.py`：

```python
import pytest

from bkflow.plugin.models import OpenPluginSpaceGrant
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


@pytest.mark.django_db
class TestOpenPluginGrant:
    def test_default_no_grant(self):
        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is False

    def test_grant_and_revoke(self):
        OpenPluginGrantService.grant(space_id=1, source_key="sops", operator="admin")
        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is True
        OpenPluginGrantService.revoke(space_id=1, source_key="sops", operator="admin")
        assert OpenPluginGrantService.is_granted(space_id=1, source_key="sops") is False

    def test_disabled_grant_is_not_granted(self):
        OpenPluginSpaceGrant.objects.create(space_id=2, source_key="sops", enabled=False, operator="admin")
        assert OpenPluginGrantService.is_granted(space_id=2, source_key="sops") is False

    def test_granted_source_keys(self):
        OpenPluginGrantService.grant(space_id=3, source_key="sops", operator="admin")
        OpenPluginGrantService.grant(space_id=3, source_key="sops2", operator="admin")
        assert set(OpenPluginGrantService.granted_source_keys(space_id=3)) == {"sops", "sops2"}
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/interface/plugin/services/test_open_plugin_grant.py -v`
Expected: FAIL，模型 / 服务不存在

- [ ] **Step 3: 新增模型**

在 `bkflow/plugin/models.py`（沿用现有开放插件模型风格：`models.Model` + `create_time/update_time`）：

```python
class OpenPluginSpaceGrant(models.Model):
    """平台级来源准入：授权某空间可接入某标准运维开放来源。"""

    space_id = models.IntegerField(verbose_name="空间ID", db_index=True)
    source_key = models.CharField(verbose_name="开放插件来源", max_length=64)
    enabled = models.BooleanField(verbose_name="是否准入", default=True)
    operator = models.CharField(verbose_name="操作人", max_length=64, blank=True, default="")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "空间开放插件来源准入"
        verbose_name_plural = "空间开放插件来源准入"
        app_label = "plugin"
        unique_together = ("space_id", "source_key")
        indexes = [models.Index(fields=["space_id", "source_key", "enabled"])]
```

- [ ] **Step 4: 生成迁移**

Run: `python manage.py makemigrations plugin -n open_plugin_space_grant`
Expected: 生成 `bkflow/plugin/migrations/0004_open_plugin_space_grant.py`（仅自动生成，不手改 schema）

- [ ] **Step 5: 实现 grant 服务**

`bkflow/plugin/services/open_plugin_grant.py`：

```python
# -*- coding: utf-8 -*-
from bkflow.plugin.models import OpenPluginSpaceGrant


class OpenPluginGrantService:
    @staticmethod
    def is_granted(space_id, source_key):
        return OpenPluginSpaceGrant.objects.filter(
            space_id=space_id, source_key=source_key, enabled=True
        ).exists()

    @staticmethod
    def granted_source_keys(space_id):
        return list(
            OpenPluginSpaceGrant.objects.filter(space_id=space_id, enabled=True).values_list("source_key", flat=True)
        )

    @staticmethod
    def grant(space_id, source_key, operator=""):
        OpenPluginSpaceGrant.objects.update_or_create(
            space_id=space_id, source_key=source_key, defaults={"enabled": True, "operator": operator}
        )

    @staticmethod
    def revoke(space_id, source_key, operator=""):
        OpenPluginSpaceGrant.objects.update_or_create(
            space_id=space_id, source_key=source_key, defaults={"enabled": False, "operator": operator}
        )
```

- [ ] **Step 6: admin 与管理命令**

`bkflow/plugin/admin.py` 注册 `OpenPluginSpaceGrant`（list_display: space_id/source_key/enabled/operator/update_time）。

`bkflow/plugin/management/commands/grant_open_plugin_source.py`：

```python
from django.core.management.base import BaseCommand

from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService


class Command(BaseCommand):
    help = "平台管理员批量授予/撤销空间对标准运维开放来源的准入"

    def add_arguments(self, parser):
        parser.add_argument("--space-ids", required=True, help="逗号分隔的空间ID")
        parser.add_argument("--source-key", required=True)
        parser.add_argument("--operator", default="admin")
        parser.add_argument("--revoke", action="store_true", help="撤销准入")

    def handle(self, *args, **options):
        space_ids = [int(x) for x in options["space_ids"].split(",") if x.strip()]
        action = OpenPluginGrantService.revoke if options["revoke"] else OpenPluginGrantService.grant
        for space_id in space_ids:
            action(space_id=space_id, source_key=options["source_key"], operator=options["operator"])
        self.stdout.write("done: {} spaces".format(len(space_ids)))
```

- [ ] **Step 7: 运行测试至通过**

Run: `pytest tests/interface/plugin/services/test_open_plugin_grant.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add bkflow/plugin/models.py \
  bkflow/plugin/migrations/0004_open_plugin_space_grant.py \
  bkflow/plugin/services/open_plugin_grant.py \
  bkflow/plugin/admin.py \
  bkflow/plugin/management/commands/grant_open_plugin_source.py \
  tests/interface/plugin/services/test_open_plugin_grant.py
git commit -m "feat(plugin): 新增平台级开放插件来源准入模型与服务 --story=133649781"
```

---

### Task 3: 第 1 层准入接入查询 / 目录 / schema 读路径

**Files:**
- Modify: `bkflow/plugin/services/open_plugin_catalog.py`
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `bkflow/apigw/views/list_plugins.py`
- Modify: `bkflow/apigw/views/get_plugin_schema.py`
- Test: `tests/interface/plugin/services/test_open_plugin_catalog.py`
- Test: `tests/interface/apigw/test_list_plugins.py`
- Test: `tests/interface/apigw/test_get_plugin_schema.py`

- [ ] **Step 1: 写「未准入空间看不到来源」失败测试**

`tests/interface/plugin/services/test_open_plugin_catalog.py` 追加：

```python
@pytest.mark.django_db
def test_ungranted_space_sees_no_source(self):
    # 没有 grant 时，list_space_plugins 不返回该来源的任何插件
    plugins = OpenPluginCatalogService.list_space_plugins(space_id=999, source_key="sops")
    assert plugins == []

@pytest.mark.django_db
def test_enable_all_blocked_without_grant(self):
    with pytest.raises(Exception):  # 或断言返回 0 / 抛业务异常
        OpenPluginCatalogService.enable_all_visible_plugins(space_id=999, source_key="sops")
```

`tests/interface/apigw/test_list_plugins.py`：未准入空间调用 `list_plugins` 时不返回该来源插件（或明确「来源未准入」提示）；已准入则按 `enabled` 返回。

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest tests/interface/plugin/services/test_open_plugin_catalog.py -v`
- `pytest tests/interface/apigw/test_list_plugins.py -v`

Expected: FAIL（当前未校验 grant）

- [ ] **Step 3: `list_space_plugins` / `enable_all` 接入 grant**

在 `bkflow/plugin/services/open_plugin_catalog.py`：

- `_get_sources(space_id, source_key)` 之后，用 `OpenPluginGrantService.granted_source_keys(space_id)` 过滤来源；未授权来源直接从结果剔除。
- `list_space_plugins`：未准入来源不进入目录合并；返回空（或仅返回已准入来源）。
- `enable_all_visible_plugins(space_id, source_key)`：开头校验 `OpenPluginGrantService.is_granted(space_id, source_key)`，未准入抛业务异常 / 返回 0，避免在未准入空间一键全开。

```python
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService

# _get_sources 内或调用处：
granted = set(OpenPluginGrantService.granted_source_keys(space_id))
sources = [s for s in sources if s["source_key"] in granted]
```

- [ ] **Step 4: `plugin_schema_service` 接入 grant**

在 `bkflow/plugin/services/plugin_schema_service.py` 的 `_list_uniform_api_plugins_from_catalog`（L333-371）起始处，用 `granted_source_keys` 限定只列已准入来源的 `(source_key, plugin_id)`；未准入来源不可见、其 schema 不可取。

- [ ] **Step 5: APIGW 查询/ schema 视图接入**

- `bkflow/apigw/views/list_plugins.py`：经由上面 service 改动自然生效；补充对显式 `source_key` 入参的 grant 校验（未准入返回空列表 + 明确 message）。
- `bkflow/apigw/views/get_plugin_schema.py`：取 schema 前校验该插件所属来源在空间已准入且 `enabled`，否则 400「插件未开放/来源未准入」。

- [ ] **Step 6: 运行测试至通过**

Run:
- `pytest tests/interface/plugin/services/test_open_plugin_catalog.py -v`
- `pytest tests/interface/apigw/test_list_plugins.py -v`
- `pytest tests/interface/apigw/test_get_plugin_schema.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add bkflow/plugin/services/open_plugin_catalog.py \
  bkflow/plugin/services/plugin_schema_service.py \
  bkflow/apigw/views/list_plugins.py \
  bkflow/apigw/views/get_plugin_schema.py \
  tests/interface/plugin/services/test_open_plugin_catalog.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py
git commit -m "feat(plugin): 查询与目录接入平台级来源准入校验 --story=133649781"
```

---

### Task 4: 四处服务端强校验（grant + enabled + available + 黑名单）

> 统一校验入口：`OpenPluginSnapshotService.validate_pipeline_tree`（`bkflow/plugin/services/open_plugin_snapshot.py` L65-72）已校验 `available` + `enabled`，本任务在其中**增加平台级 grant 守卫**，并确保「查询 / 模板保存 / 任务创建 / 任务启动」四处都经过它。

**Files:**
- Modify: `bkflow/plugin/services/open_plugin_snapshot.py`
- Modify: `bkflow/template/serializers/template.py`（确认模板保存调用校验）
- Modify: `bkflow/apigw/views/create_task.py`
- Modify: `bkflow/apigw/views/operate_task.py`
- Modify: `bkflow/task/views.py` / `bkflow/task/operations.py`（内部 REST 创建/启动）
- Test: `tests/interface/plugin/services/test_open_plugin_snapshot.py`
- Test: `tests/interface/apigw/test_create_task.py`
- Test: `tests/interface/apigw/test_operate_task.py`

- [ ] **Step 1: 写校验失败测试**

`tests/interface/plugin/services/test_open_plugin_snapshot.py`：

```python
@pytest.mark.django_db
def test_validate_rejects_when_source_not_granted(self):
    # 插件 available + 空间 enabled，但来源未 grant → 仍拒绝
    space_id = self._setup_available_and_enabled_plugin()  # 夹具：catalog AVAILABLE + availability enabled
    # 未创建 OpenPluginSpaceGrant
    with pytest.raises(serializers.ValidationError):
        OpenPluginSnapshotService.validate_pipeline_tree(space_id=space_id, pipeline_tree=self._tree_with_open_plugin())

@pytest.mark.django_db
def test_validate_passes_when_granted(self):
    space_id = self._setup_available_and_enabled_plugin()
    OpenPluginGrantService.grant(space_id=space_id, source_key="sops", operator="admin")
    OpenPluginSnapshotService.validate_pipeline_tree(space_id=space_id, pipeline_tree=self._tree_with_open_plugin())
```

`tests/interface/apigw/test_create_task.py` / `test_operate_task.py`：未准入空间用引用开放插件的模板建任务 / 启动任务 → 400 拒绝；准入后通过。

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest tests/interface/plugin/services/test_open_plugin_snapshot.py -v`
- `pytest tests/interface/apigw/test_create_task.py -v`
- `pytest tests/interface/apigw/test_operate_task.py -v`

Expected: FAIL（grant 守卫尚未加入）

- [ ] **Step 3: 在 `validate_pipeline_tree` 增加 grant 守卫**

`bkflow/plugin/services/open_plugin_snapshot.py`：

```python
from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService

@classmethod
def validate_pipeline_tree(cls, space_id, pipeline_tree):
    for ref in cls.collect_plugin_references(space_id=space_id, pipeline_tree=pipeline_tree, include_unmatched=True):
        if ref["catalog"] is None:
            raise serializers.ValidationError("开放插件 [{}] 不存在或已下线".format(ref["plugin_id"]))
        if not OpenPluginGrantService.is_granted(space_id, ref["catalog"].source_key):
            raise serializers.ValidationError("开放插件来源 [{}] 未对当前空间准入".format(ref["catalog"].source_key))
        if ref["catalog"].status != OpenPluginCatalogIndex.Status.AVAILABLE:
            raise serializers.ValidationError("开放插件 [{}] 当前不可用".format(ref["plugin_id"]))
        if not ref["enabled"]:
            raise serializers.ValidationError("开放插件 [{}] 在当前空间未开放".format(ref["plugin_id"]))
```

> `collect_plugin_references` 的 `ref["catalog"]` 已含 `source_key`（`OpenPluginCatalogIndex`）。若黑名单（do_not_open_list）信息由标准运维侧目录同步带回 catalog，可在此追加「不在黑名单」判断；否则黑名单在标准运维侧登记期 4xx 拦截，BKFlow 侧呈现为「不可用」。

- [ ] **Step 4: 确认四处都过校验**

- **查询**：Task 3 已覆盖（目录/schema）。
- **模板保存**：`bkflow/template/serializers/template.py:145` 已调用 `validate_pipeline_tree`，grant 守卫随之生效（补一条空间未准入的保存被拒测试）。
- **任务创建**：`bkflow/apigw/views/create_task.py` 校验模板 pipeline 时调用 `validate_pipeline_tree`；`bkflow/task/views.py` 内部创建路径补同样调用（`CreateTaskInstanceSerializer.validate` 或 view 内）。
- **任务启动**：`bkflow/apigw/views/operate_task.py`（`operation=="start"` 分支）与 `bkflow/task/operations.py` 的 `TaskOperation.start` 在派发前调用 `validate_pipeline_tree`（取任务快照 pipeline）。

抽出复用工具（如已有则复用），避免四处重复实现：

```python
# 统一调用点（示意）：
OpenPluginSnapshotService.validate_pipeline_tree(space_id=space_id, pipeline_tree=pipeline_tree)
```

- [ ] **Step 5: 运行测试至通过**

Run:
- `pytest tests/interface/plugin/services/test_open_plugin_snapshot.py -v`
- `pytest tests/interface/apigw/test_create_task.py -v`
- `pytest tests/interface/apigw/test_operate_task.py -v`
- `pytest tests/interface/template -v`（模板保存回归，按实际路径）

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/plugin/services/open_plugin_snapshot.py \
  bkflow/template/serializers/template.py \
  bkflow/apigw/views/create_task.py \
  bkflow/apigw/views/operate_task.py \
  bkflow/task/views.py \
  bkflow/task/operations.py \
  tests/interface/plugin/services/test_open_plugin_snapshot.py \
  tests/interface/apigw/test_create_task.py \
  tests/interface/apigw/test_operate_task.py
git commit -m "feat(plugin): 模板保存/建任务/启动任务接入两层准入强校验 --story=133649781"
```

---

### Task 5: 存量空间迁移（默认授予已配置来源的 grant）

> 目标：对**已配置标准运维 `uniform_api` 来源**的存量空间默认授予 grant，避免现有第三方插件能力断流（spec §4.3）。新空间默认无 grant（保守）。

**Files:**
- Create: `bkflow/plugin/migrations/0005_backfill_open_plugin_grant.py`
- Test: `tests/interface/plugin/services/test_open_plugin_grant.py`（追加迁移逻辑的单元测试）

- [ ] **Step 1: 写迁移逻辑失败测试**

把迁移核心逻辑抽到 `OpenPluginGrantService.backfill_existing_sources()`（便于测试），先写测试：

```python
@pytest.mark.django_db
def test_backfill_grants_existing_source_spaces(self):
    self._setup_space_with_uniform_api_source(space_id=7, source_key="sops")  # 夹具：SpaceConfig 配了 sops 来源
    created = OpenPluginGrantService.backfill_existing_sources()
    assert created >= 1
    assert OpenPluginGrantService.is_granted(space_id=7, source_key="sops") is True
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/interface/plugin/services/test_open_plugin_grant.py -v`
Expected: FAIL，`backfill_existing_sources` 不存在

- [ ] **Step 3: 实现 backfill 逻辑**

在 `bkflow/plugin/services/open_plugin_grant.py` 增加：

```python
@classmethod
def backfill_existing_sources(cls):
    """为已配置标准运维 uniform_api 来源的存量空间默认授予 grant。"""
    from bkflow.plugin.services.open_plugin_catalog import OpenPluginCatalogService
    created = 0
    for space_id, source_key in OpenPluginCatalogService.iter_configured_sources():
        _, is_created = OpenPluginSpaceGrant.objects.get_or_create(
            space_id=space_id, source_key=source_key, defaults={"enabled": True, "operator": "migration"}
        )
        created += int(is_created)
    return created
```

在 `OpenPluginCatalogService` 增加 `iter_configured_sources()`：遍历 `SpaceConfig` 中配置了 `UniformApiConfig` 开放来源的空间，`yield (space_id, source_key)`（复用现有 `_get_sources` 的读取逻辑，去掉 grant 过滤）。

- [ ] **Step 4: 写数据迁移**

`bkflow/plugin/migrations/0005_backfill_open_plugin_grant.py`：

```python
from django.db import migrations


def forwards(apps, schema_editor):
    from bkflow.plugin.services.open_plugin_grant import OpenPluginGrantService
    OpenPluginGrantService.backfill_existing_sources()


def backwards(apps, schema_editor):
    # 撤销迁移授予的 grant（operator == "migration"）
    OpenPluginSpaceGrant = apps.get_model("plugin", "OpenPluginSpaceGrant")
    OpenPluginSpaceGrant.objects.filter(operator="migration").delete()


class Migration(migrations.Migration):
    dependencies = [("plugin", "0004_open_plugin_space_grant")]
    operations = [migrations.RunPython(forwards, backwards)]
```

> 数据迁移内调用 service 读 `SpaceConfig` 时注意：迁移环境用真实模型即可（service 已是普通查询）；若 CI 对迁移内 import app 代码敏感，可把读取逻辑内联到迁移函数。

- [ ] **Step 5: 运行测试至通过**

Run:
- `pytest tests/interface/plugin/services/test_open_plugin_grant.py -v`
- `python manage.py migrate plugin --plan`（确认迁移可被识别）

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bkflow/plugin/services/open_plugin_grant.py \
  bkflow/plugin/services/open_plugin_catalog.py \
  bkflow/plugin/migrations/0005_backfill_open_plugin_grant.py \
  tests/interface/plugin/services/test_open_plugin_grant.py
git commit -m "feat(plugin): 存量已配置来源空间默认授予开放插件准入 --story=133649781"
```

---

### Task 6: 空间治理接口对齐 + APIGW 文档同步

**Files:**
- Modify: `bkflow/space/views.py` / `bkflow/space/serializers.py` / `bkflow/space/urls.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`（仅当接口签名/错误码有对外变化）
- Modify: `bkflow/apigw/docs/zh/list_plugins.md` / `get_plugin_schema.md` / `create_task.md` / `operate_task.md`
- Modify: `bkflow/apigw/docs/apigw-docs.zip`
- Test: `tests/interface/space/test_space_views.py`

- [ ] **Step 1: 写空间治理失败测试**

`tests/interface/space/test_space_views.py`：

```python
@pytest.mark.django_db
def test_space_open_plugin_list_shows_only_granted_source(self):
    space_id = self._setup_space_with_catalog(source_key="sops")  # SpaceConfig 配 sops 来源 + catalog 有插件
    # 未准入 → 列表不含该来源
    resp = self.client.get("/space/{}/list_open_plugins/".format(space_id))
    assert all(item["source_key"] != "sops" for item in resp.json()["data"])
    # 准入后 → 列表含该来源且带 granted 标记
    OpenPluginGrantService.grant(space_id=space_id, source_key="sops", operator="admin")
    resp = self.client.get("/space/{}/list_open_plugins/".format(space_id))
    sops_items = [i for i in resp.json()["data"] if i["source_key"] == "sops"]
    assert sops_items and sops_items[0]["granted"] is True

@pytest.mark.django_db
def test_enable_all_only_in_granted_space(self):
    space_id = self._setup_space_with_catalog(source_key="sops")
    resp = self.client.post("/space/{}/enable_all_open_plugins/".format(space_id), data={"source_key": "sops"})
    assert resp.status_code == 400  # 未准入被拒
    OpenPluginGrantService.grant(space_id=space_id, source_key="sops", operator="admin")
    resp = self.client.post("/space/{}/enable_all_open_plugins/".format(space_id), data={"source_key": "sops"})
    assert resp.status_code == 200
```

> `_setup_space_with_catalog` 为测试夹具：写入 `SpaceConfig` 的 `UniformApiConfig` 来源 + `OpenPluginCatalogIndex`(AVAILABLE)；接口路径以 `bkflow/space/urls.py` 实际为准。

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/interface/space/test_space_views.py -v`
Expected: FAIL

- [ ] **Step 3: 空间治理接口体现 grant**

在 `bkflow/space/views.py` 的 `SpaceConfigAdminViewSet`（`list_open_plugins` / `toggle` / `enable_all` / `disable_source`）：

- 列表只展示「已准入来源」的插件；为每个来源附带 `granted=True`。
- `toggle` / `enable_all` 在未准入来源上拒绝（复用 `OpenPluginGrantService.is_granted`）。
- 权限沿用空间管理员 / 超管。

> 平台级「授予哪些空间可接入来源」由 Task 2 的 admin + management command 承担；如产品需要对外 REST，再单独加平台管理员 viewset（本期以 admin + command 为准，spec §4.1「轻量管理 API」）。

- [ ] **Step 4: APIGW 资源与文档同步**

按 `.ai/rules/apigw-resource-sync.mdc`：

- 若 `list_plugins / get_plugin_schema / create_task / operate_task` 的对外请求/响应（如新增「来源未准入」错误码）有变化，更新 `bkflow/apigw/management/commands/data/api-resources.yml` 与对应 `bkflow/apigw/docs/zh/*.md`。
- 运行 `bash scripts/apigw_docs.sh` 重生成 `bkflow/apigw/docs/apigw-docs.zip`。
- 若无对外签名变化，仅在文档补充「两层准入」说明。

- [ ] **Step 5: 运行测试至通过**

Run: `pytest tests/interface/space/test_space_views.py -v`
Expected: PASS，且 `apigw-docs.zip` 已刷新

- [ ] **Step 6: Commit**

```bash
git add bkflow/space/views.py bkflow/space/serializers.py bkflow/space/urls.py \
  bkflow/apigw/management/commands/data/api-resources.yml \
  bkflow/apigw/docs/zh/list_plugins.md bkflow/apigw/docs/zh/get_plugin_schema.md \
  bkflow/apigw/docs/zh/create_task.md bkflow/apigw/docs/zh/operate_task.md \
  bkflow/apigw/docs/apigw-docs.zip \
  tests/interface/space/test_space_views.py
git commit -m "feat(space): 空间治理对齐两层准入并同步 APIGW 文档 --story=133649781"
```

---

### Task 7: 自检与回归（含联调清单）

**Files:**
- Verify: 上述全部改动

- [ ] **Step 1: 组件与协议回归**

Run:
- `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`
- `pytest tests/plugins/uniform_api/test_uniform_api_client.py -v`

Expected: PASS，v1/v2/v3 不受影响，老来源不带 context 仍可执行

- [ ] **Step 2: 准入与校验回归**

Run:
- `pytest tests/interface/plugin/services -v`
- `pytest tests/interface/apigw/test_list_plugins.py tests/interface/apigw/test_get_plugin_schema.py tests/interface/apigw/test_create_task.py tests/interface/apigw/test_operate_task.py -v`
- `pytest tests/interface/space/test_space_views.py -v`

Expected: PASS

- [ ] **Step 3: 自检清单逐条确认（见文末 Verification Checklist）**

- [ ] **Step 4: 联调清单（与标准运维侧共同覆盖，spec §7 联调验收）**

1. 正常链路：平台 grant → 空间开插件 → 存模板 → 建任务 → 执行成功（内置、第三方各一）
2. 异步三模式：同步 / 轮询 / 回调
3. 业务上下文：biz 空间能跑依赖 `project` 的内置插件（如 JOB 执行作业）
4. 身份：operator 无权限被标准运维侧底层系统正确拒绝
5. 异常：project 解析失败 / 命中黑名单 / 版本失效 / 回调失败 / 超时兜底
6. 未准入空间看不到该来源；撤销 grant 后存量模板可看不可新建任务

- [ ] **Step 5: Commit（如有修补）**

```bash
git add -A
git commit -m "test(plugin): 全量插件能力两层准入回归与修补 --story=133649781"
```

---

## 当前交付边界（实事求是）

- ✅ `uniform_api v4.0.0` execute 向后兼容透传 `context`（不升版本）
- ✅ 两层准入：平台 `OpenPluginSpaceGrant` + 空间 `SpaceOpenPluginAvailability`
- ✅ 查询 / 模板保存 / 任务创建 / 任务启动四处服务端强校验
- ✅ 存量已配置来源空间默认授 grant，新空间保守默认无 grant
- ✅ 前端协作补充：按最新 `prototype-wireframe` 规范补充节点使用 API 插件时新增“版本”选择项的最小 wiremd 线框
- ⏳ 依赖项：
  1. 真正「使用全部插件」依赖标准运维侧组件运行壳落地（见 bk-sops 计划）
  2. operator 权限是产品前提（BKFlow 用户需在对应业务有权限）
  3. 黑名单（不开放）以标准运维侧为权威，BKFlow 呈现「不可用」

---

## Self-Review（spec 覆盖核对）

| spec 章节 | 对应 Task |
|---|---|
| §3 协议扩展 `context` | Task 1 |
| §4.1 第 1 层来源准入（`OpenPluginSpaceGrant`） | Task 2 |
| §4.2 第 2 层 per-plugin（复用 `SpaceOpenPluginAvailability`） | Task 3 / 6 |
| §4.3 默认与迁移 | Task 5 |
| §5 四处服务端强校验 | Task 3（查询）+ Task 4（保存/建/启） |
| §6 上下文构造来源 | Task 1 |
| §7 测试与验收 + 联调 | 各 Task TDD + Task 7 |
| §8 兼容与迁移（协议/grant/APIGW） | Task 1 / 5 / 6 |
| §9 风险与后续 | 交付边界 + 联调清单 |

---

## Verification Checklist

- execute body 携带 `context`；老来源不带 context 时仍可正常执行（兼容回归）
- 两层准入：未准入空间看不到该来源；准入后 per-plugin 开关生效
- 一键全开仅在已准入空间生效
- 四处服务端强校验生效（不仅前端隐藏）
- 撤销 grant 后存量模板可查看、不可新建任务
- 快照与版本治理回归不退化
- `OpenPluginSpaceGrant` 迁移 + 存量空间默认授 grant 生效
- 任何 `bkflow/apigw/` 改动已同步 `api-resources.yml` + docs zip（`bash scripts/apigw_docs.sh`）
- 前端原型只覆盖 V4.0.0 节点 API 插件新增“版本”选择项，避免引入调度模式、历史版本治理、版本差异对比等额外 UI
- 前端对接文档明确 `context` 不入表单、不保存节点，由 BKFlow runtime execute 时注入

---

## Notes For Executor

- 推荐顺序：Task 1 → 2 → 3 → 4 → 5 → 6 → 7。先打通协议与准入模型，再叠加读路径与四处校验，最后迁移与文档。
- 测试统一用 `pytest <path> -v`（`pytest.ini` 已设 `DJANGO_SETTINGS_MODULE=settings`）。
- BKFlow 只透传 `context`，**不要在 BKFlow 侧解析 sops project**；解析在标准运维侧（见 bk-sops 计划 Task 3）。
- 与标准运维侧计划存在执行顺序耦合：BKFlow 透传 `context` 后，端到端「用全部插件」需标准运维侧运行壳同步落地，建议两仓按联调清单同步推进。
