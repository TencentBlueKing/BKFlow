# SOPS Open Plugin PR 698 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 PR #698 中开放插件准入绕过、目录授权顺序、历史配置回填、同步取消和回调入参校验问题。

**Architecture:** 所有治理校验继续留在 interface 模块，engine 只管理运行态回调和取消引用。创建任务入口共享快照服务，启动入口统一在调用 engine 前重新校验；远端取消由 engine Celery 任务异步执行，历史 migration 文件保持不变并通过稳定的 Service 容错保证可重放。

**Tech Stack:** Django 3.2、DRF、Celery、pytest、BKFlow interface/engine 模块

**Spec:** `docs/specs/2026-06-26-sops-open-plugin-full-capability-design.md`

## Global Constraints

- 不允许 engine 依赖 `bkflow.plugin` 的 interface-only ORM 表。
- 不修改已存在的 migration 操作逻辑；历史兼容通过运行时 Service 修复。
- `bkflow/apigw/` 代码变更必须同步资源定义、中文文档和 `apigw-docs.zip`。
- 每项生产代码改动前先运行对应失败测试。
- 不从 `develop` 合入代码，所有变更留在 `feat/sops-open-plugin-backend`。

---

### Task 1: 统一任务创建与启动预检

**Files:**
- Modify: `bkflow/plugin/services/open_plugin_snapshot.py`
- Modify: `bkflow/template/views/template.py`
- Modify: `bkflow/interface/task/view.py`
- Modify: `bkflow/apigw/views/create_task.py`
- Modify: `bkflow/apigw/views/create_task_by_app.py`
- Modify: `bkflow/apigw/views/operate_task.py`
- Modify: `bkflow/apigw/views/operate_task_by_app.py`
- Test: `tests/interface/template/test_template_views.py`
- Test: `tests/interface/task/test_task_views.py`
- Test: `tests/interface/apigw/test_create_task.py`
- Test: `tests/interface/apigw/test_operate_task.py`

**Interfaces:**
- Produces: `OpenPluginSnapshotService.prepare_task_extra_info(space_id, pipeline_tree, extra_info, username, scope_type, scope_id) -> dict`
- Consumes: existing `validate_pipeline_tree`, `build_reference_snapshot`, `build_schema_snapshot`, and `merge_snapshots` methods.

- [x] Add Web and by-app create/start tests proving revoked or disabled plugins stop before `TaskComponentClient.create_task/operate_task`.
- [x] Run only those tests and confirm they fail because the client is still called.
- [x] Add the shared task-extra preparation method and call it from every create path; call `validate_pipeline_tree` from every start path after fetching task detail.
- [x] Re-run the focused tests and existing main APIGW tests until green.

### Task 2: Enforce source grants before catalog mode dispatch

**Files:**
- Modify: `bkflow/pipeline_plugins/query/uniform_api/uniform_api.py`
- Test: `tests/interface/test_uniform_api_catalog_mode.py`

**Interfaces:**
- Consumes: `OpenPluginGrantService.is_granted(space_id, source_key)` and the effective `source_key = api_entry.source_key or api_name` rule.
- Produces: identical empty-catalog response for ungranted sources in remote, cache-first, and cache-only modes.

- [x] Add tests that configure default/explicit remote mode without a grant and assert the remote client is not called.
- [x] Run the new tests and confirm the current early remote return makes them fail.
- [x] Resolve source identity and check the grant before branching on catalog mode; protect metadata lookup with the same configured-source check.
- [x] Re-run catalog-mode, list, schema, and detail tests.

### Task 3: Make historical grant backfill tolerant of invalid rows

**Files:**
- Modify: `bkflow/plugin/services/open_plugin_catalog.py`
- Test: `tests/interface/plugin/services/test_open_plugin_catalog.py`

**Interfaces:**
- Produces: `iter_configured_sources()` skips and logs one invalid `SpaceConfig` while continuing to yield valid sources.
- Consumes: existing `UniformAPIConfigHandler.handle()` parsing and `OpenPluginGrantService.backfill_existing_sources()`.

- [x] Add a mixed valid/invalid configuration test that expects the valid source to be backfilled.
- [x] Run it and confirm parsing the invalid row aborts iteration.
- [x] Catch the configuration validation exception per row, log the space id, and continue; keep migration files unchanged.
- [x] Re-run catalog service and plugin migration-related tests.

### Task 4: Dispatch open-plugin cancellation asynchronously

**Files:**
- Modify: `bkflow/task/operations.py`
- Modify: `bkflow/task/celery/tasks.py`
- Test: `tests/engine/task/test_task_operations.py`
- Test: `tests/engine/task/test_node_operations.py`
- Test: `tests/engine/task/test_celery_tasks.py`

**Interfaces:**
- Produces: Celery task `cancel_open_plugin_runs(task_id: int, operator: str, node_id: str = "")`.
- Consumes: `TaskInstance`, unconsumed `OpenPluginRunCallbackRef` rows, one task-level space-config fetch, and `_get_open_plugin_cancel_credential`.

- [x] Change revoke/forced-fail tests to require task dispatch and no inline HTTP cancellation.
- [x] Run them and confirm the current synchronous functions are called.
- [x] Add an idempotent Celery worker, load configs once per task, and dispatch it after successful engine revoke/forced-fail.
- [x] Add worker tests covering missing task, task-wide filtering, node filtering, and per-run failure continuation.
- [x] Re-run task operation, node operation, and Celery task suites.

### Task 5: Validate callback payloads and synchronize APIGW artifacts

**Files:**
- Modify: `bkflow/apigw/views/operate_task_node.py`
- Modify: `bkflow/apigw/serializers/task.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Modify: `bkflow/apigw/docs/zh/operate_task_node.md`
- Regenerate: `bkflow/apigw/docs/apigw-docs.zip`
- Test: `tests/interface/apigw/test_operate_task_node.py`

**Interfaces:**
- Produces: a dedicated open-plugin callback serializer requiring `open_plugin_run_id` and `status`, with optional output/error/truncation fields.
- Consumes: existing engine-side token and callback-reference verification.

- [x] Add a missing-status request test expecting a structured 400 and no engine call.
- [x] Run it and confirm the current `data["status"]` access returns 500.
- [x] Validate the open-plugin branch with the dedicated serializer before forwarding.
- [x] Update the APIGW request schema and Chinese documentation, then regenerate the docs archive.
- [x] Re-run callback interface and engine tests.

### Task 6: Final verification

**Files:**
- Verify all modified production, test, documentation, and generated APIGW files.

- [x] Run the complete open-plugin interface/plugin/APIGW regression set.
- [x] Run engine task operation, node operation, and Celery task regression sets.
- [x] Run Black, Flake8, relevant frontend checks if frontend files changed, and `git diff --check` on the fix diff.
- [x] Review `git diff upstream/master...HEAD` and the local fix diff for route coverage, engine/interface ownership, credential handling, and migration compatibility.

### Task 7: Resolve upstream master conflicts and validate release compatibility

**Files:**
- Merge: `upstream/master`
- Resolve: `frontend/src/assets/fonts/bksops-icon.svg`
- Resolve: `frontend/src/views/task/TaskExecute/SideDrawerExecuteInfo.vue`
- Resolve: `frontend/src/views/template/TemplateEdit/NodeConfig/InputParams.vue`
- Resolve: `frontend/src/views/template/TemplateEdit/NodeConfig/NodeConfig.vue`
- Resolve: `frontend/src/views/template/TemplateMock/MockSetting/index.vue`
- Verify: interface/engine migrations, API serializers, frontend open-plugin form, and existing task/template behavior

**Interfaces:**
- Preserves: upstream SubCanvas node editing and execution UI behavior.
- Preserves: open-plugin `source_key`, schema, context, callback, cancellation, and catalog authorization behavior.
- Produces: a mergeable PR head based on the current `upstream/master` without importing `develop` history.

- [x] Merge `upstream/master` into `feat/sops-open-plugin-backend` and confirm the conflict set matches the read-only `git merge-tree` result.
- [x] Resolve each Vue conflict by retaining upstream SubCanvas branches and adding the open-plugin props/data flow at the common call site.
- [x] Keep the complete upstream icon-font asset set and normalize the merged SVG; verify the legacy and SubCanvas glyphs are both present.
- [x] Run frontend unit tests, full ESLint, and a development build for the conflict-resolved tree.
- [x] Run the focused interface/plugin/APIGW and engine task regression suites against the merged tree.
- [x] Inspect migrations, route/serializer contracts, configuration defaults, Celery scheduling, and rollback behavior; record backward-compatible defaults and release gates.
- [ ] Commit and push the merge resolution, then verify PR #698 is no longer `CONFLICTING`.

#### Release compatibility result

- Existing uniform API v1/v2/v3 configurations and task nodes remain on their original remote/v3 paths; the v4 runtime is selected only when an open-plugin identity is present.
- New model fields use defaults and new API fields/resources are additive. The APIGW inventory has no removed path/method pairs or duplicate `operationId`; existing backend/auth settings are unchanged.
- Deploy engine migrations and engine code/workers before interface migrations and interface/web/beat. Do not enable open plugins before both modules are healthy.
- The statistics migration adds indexed columns and rebuilds one unique constraint, so production table size and DDL lock time must be checked before release.
- The interface beat process starts one catalog-dispatch cycle every 30 minutes. Keep the default rate limit and monitor downstream list-API latency/error rate during the first cycles.
- Rolling back before enabling v4 plugins is safe while leaving additive tables in place. After v4 tasks exist, an old engine cannot continue those nodes; disable new v4 task creation and drain or terminate v4 runs before a code rollback.
