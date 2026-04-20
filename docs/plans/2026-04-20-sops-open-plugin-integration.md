# 标准运维开放插件生态接入 BKFlow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 BKFlow 通过 `uniform_api` 使用标准运维开放出来的内置插件与第三方插件生态，并补齐空间治理、业务版本治理、回调安全、快照与迁移能力。

**Architecture:** 标准运维新增 `open_plugins` 开放层，对外提供统一的目录与执行网关，并在自身内部完成插件元数据适配、上下文转换、幂等执行与独立 worker 调度。BKFlow 不新增第四种插件类型，而是在现有 `uniform_api` 体系上引入 `v4.0.0` 协议、开放插件目录本地索引、空间级开放管理、执行回调鉴权与插件快照治理。

**Tech Stack:** Django, DRF, Celery, `uniform_api` wrapper, BKFlow APIGW, pytest, Django TestCase, BlueKing plugin service / component framework

**Spec:** `docs/specs/2026-04-20-sops-open-plugin-integration-design.md`

---

## File Structure

```text
BKFlow
├── bkflow/pipeline_plugins/query/uniform_api/utils.py
│   └── 扩展 uniform_api v4.0.0 list/detail meta 协议校验
├── bkflow/pipeline_plugins/query/uniform_api/uniform_api.py
│   └── 扩展版本化 meta 获取、本地目录索引读取与来源查询逻辑
├── bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py
│   └── 新增开放插件运行时包装器，透传 plugin_version / client_request_id / callback_* / polling
├── bkflow/pipeline_plugins/components/collections/uniform_api/__init__.py
│   └── 注册 v4.0.0 包装器
├── bkflow/plugin/models.py
│   └── 新增 OpenPluginCatalogIndex / SpaceOpenPluginAvailability / OpenPluginRunCallbackRef
├── bkflow/plugin/services/
│   ├── plugin_schema_service.py
│   ├── open_plugin_catalog.py
│   └── open_plugin_snapshot.py
│       └── 目录索引、空间治理、快照与版本状态服务
├── bkflow/space/configs.py
│   └── 扩展 UniformApiConfig 配置结构，声明开放插件来源
├── bkflow/space/serializers.py
├── bkflow/space/views.py
├── bkflow/space/urls.py
│   └── 新增空间级开放插件管理接口
├── bkflow/apigw/serializers/plugin.py
├── bkflow/apigw/views/list_plugins.py
├── bkflow/apigw/views/get_plugin_schema.py
├── bkflow/apigw/views/create_task.py
├── bkflow/apigw/views/operate_task_node.py
│   └── 补齐 plugin_version、回调 token 校验、服务端开放状态校验
├── bkflow/apigw/management/commands/data/api-resources.yml
├── bkflow/apigw/docs/zh/list_plugins.md
├── bkflow/apigw/docs/zh/get_plugin_schema.md
├── bkflow/apigw/docs/zh/operate_task_node.md
├── bkflow/apigw/docs/apigw-docs.zip
├── bkflow/template/models.py
├── bkflow/template/serializers/template.py
├── bkflow/task/models.py
├── bkflow/statistics/models.py
├── bkflow/plugin/migrations/0002_open_plugin_catalog_index.py
└── tests/
    ├── plugins/uniform_api/test_uniform_api_client.py
    ├── plugins/components/collections/uniform_api_test/test_v4_0_0.py
    ├── interface/plugin/services/test_plugin_schema_service.py
    ├── interface/space/test_space_views.py
    ├── interface/apigw/test_list_plugins.py
    ├── interface/apigw/test_get_plugin_schema.py
    └── interface/apigw/test_operate_task_node.py

Standard Ops (`../bk-sops`)
├── gcloud/open_plugins/
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   ├── constants.py
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── tasks.py
│   └── services/
│       ├── catalog.py
│       ├── execution.py
│       ├── context.py
│       └── callbacks.py
│           └── 目录聚合、执行适配、上下文回退、回调桥接
├── config/default.py
├── config/urls_custom.py
├── gcloud/taskflow3/celery/settings.py
├── gcloud/taskflow3/celery/tasks.py
├── plugin_service/api.py
├── gcloud/open_plugins/migrations/0001_initial.py
└── gcloud/tests/open_plugins/
    ├── test_catalog_views.py
    ├── test_execution_gateway.py
    ├── test_callback_bridge.py
    └── test_context_fallback.py
```

**Files NOT changed:**
- `bkflow/pipeline_plugins/components/collections/uniform_api/v1_0_0.py`
- `bkflow/pipeline_plugins/components/collections/uniform_api/v2_0_0.py`
- `bkflow/pipeline_plugins/components/collections/uniform_api/v3_0_0.py`
- `bkflow/utils/a2flow.py`

---

### Task 1: BKFlow `uniform_api v4.0.0` 协议骨架

**Files:**
- Create: `bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py`
- Modify: `bkflow/pipeline_plugins/components/collections/uniform_api/__init__.py`
- Modify: `bkflow/pipeline_plugins/query/uniform_api/utils.py`
- Modify: `bkflow/pipeline_plugins/query/uniform_api/uniform_api.py`
- Test: `tests/plugins/uniform_api/test_uniform_api_client.py`
- Test: `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py`

- [ ] **Step 1: 为 v4 协议写失败测试**

在 `tests/plugins/uniform_api/test_uniform_api_client.py` 新增最小测试，覆盖：

```python
def test_validate_v4_list_meta_contract():
    client = UniformAPIClient()
    data = {
        "total": 1,
        "apis": [
            {
                "id": "open_plugin_001",
                "name": "JOB 执行作业",
                "plugin_source": "builtin",
                "plugin_code": "job_execute_task",
                "wrapper_version": "v4.0.0",
                "default_version": "1.2.0",
                "latest_version": "1.3.0",
                "versions": ["1.2.0", "1.3.0"],
                "meta_url_template": "https://bk-sops.example/open-plugins/open_plugin_001?version={version}",
            }
        ],
    }
    client.validate_response_data(data, client.UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA)
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/plugins/uniform_api/test_uniform_api_client.py -v`
Expected: FAIL，提示 `UNIFORM_API_LIST_RESPONSE_DATA_SCHEMA` / `UNIFORM_API_META_RESPONSE_DATA_SCHEMA` 不识别 v4 字段

- [ ] **Step 3: 扩展 `UniformAPIClient` 协议校验**

在 `bkflow/pipeline_plugins/query/uniform_api/utils.py`：

- 为 `list_meta` 增加 `plugin_source`、`plugin_code`、`wrapper_version`、`default_version`、`latest_version`、`versions`、`meta_url_template`
- 为 `detail_meta` 增加 `plugin_version`、`plugin_source`、`plugin_code`
- 明确 `polling.success_tag` / `fail_tag` / `running_tag` 继续沿用 v3 对象结构
- 不改 v2/v3 字段兼容行为

- [ ] **Step 4: 新建 `v4_0_0.py` 最小包装器**

复制 `v3_0_0.py` 的最小运行骨架，先补齐 v4 独有输入输出字段：

```python
extra_data.update(
    {
        "plugin_id": data.get_one_of_inputs("uniform_api_plugin_id"),
        "plugin_version": data.get_one_of_inputs("uniform_api_plugin_version"),
        "client_request_id": data.get_one_of_inputs("uniform_api_client_request_id"),
    }
)
```

先保证模块可被加载，不在本任务引入完整回调逻辑。

- [ ] **Step 5: 注册 v4 包装器**

在 `bkflow/pipeline_plugins/components/collections/uniform_api/__init__.py` 导出 `v4_0_0`，保持 v1/v2/v3 不变。

- [ ] **Step 6: 跑通过协议与包装器测试**

Run:
- `pytest tests/plugins/uniform_api/test_uniform_api_client.py -v`
- `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`

Expected: PASS，且不影响 v1/v2/v3 既有测试

- [ ] **Step 7: Commit**

```bash
git add bkflow/pipeline_plugins/query/uniform_api/utils.py \
  bkflow/pipeline_plugins/query/uniform_api/uniform_api.py \
  bkflow/pipeline_plugins/components/collections/uniform_api/__init__.py \
  bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py \
  tests/plugins/uniform_api/test_uniform_api_client.py \
  tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py
git commit -m "feat(uniform_api): 新增开放插件 v4 协议骨架 --story=133649781"
```

---

### Task 2: 标准运维开放插件目录应用骨架

**Files:**
- Create: `../bk-sops/gcloud/open_plugins/__init__.py`
- Create: `../bk-sops/gcloud/open_plugins/apps.py`
- Create: `../bk-sops/gcloud/open_plugins/urls.py`
- Create: `../bk-sops/gcloud/open_plugins/constants.py`
- Create: `../bk-sops/gcloud/open_plugins/models.py`
- Create: `../bk-sops/gcloud/open_plugins/serializers.py`
- Create: `../bk-sops/gcloud/open_plugins/views.py`
- Create: `../bk-sops/gcloud/open_plugins/services/catalog.py`
- Modify: `../bk-sops/config/default.py`
- Modify: `../bk-sops/config/urls_custom.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_catalog_views.py`

- [ ] **Step 1: 为目录接口写失败测试**

在 `../bk-sops/gcloud/tests/open_plugins/test_catalog_views.py` 覆盖：

- `GET /open-plugins/categories`
- `GET /open-plugins`
- `GET /open-plugins/{plugin_id}?version=1.2.0`

最小断言：

```python
assert data["result"] is True
assert data["data"]["apis"][0]["wrapper_version"] == "v4.0.0"
assert data["data"]["apis"][0]["versions"]
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest ../bk-sops/gcloud/tests/open_plugins/test_catalog_views.py -v`
Expected: FAIL，提示模块或 URL 不存在

- [ ] **Step 3: 创建 `open_plugins` app 骨架并挂路由**

在 `../bk-sops/config/default.py` 注册 `gcloud.open_plugins`，在 `../bk-sops/config/urls_custom.py` 增加：

```python
re_path(r"^", include("gcloud.open_plugins.urls"))
```

`urls.py` 先暴露：

- `^open-plugins/categories$`
- `^open-plugins$`
- `^open-plugins/(?P<plugin_id>[^/]+)$`

- [ ] **Step 4: 实现目录聚合骨架**

在 `services/catalog.py` 中提供：

- `list_categories()`
- `list_plugins()`
- `get_plugin_detail(plugin_id, version)`

第一版先只拉通内置插件与第三方插件的空壳数据，统一返回 v4 协议字段，`versions` 可先从现有插件元数据推导。

- [ ] **Step 5: 实现 DRF/View 层**

在 `views.py` / `serializers.py` 中补齐：

- app 接入鉴权
- `plugin_id` / `version` 参数校验
- 统一 `result/data/message` 响应格式

- [ ] **Step 6: 跑目录测试**

Run: `pytest ../bk-sops/gcloud/tests/open_plugins/test_catalog_views.py -v`
Expected: PASS，返回的 `list_meta` / `detail_meta` 满足 `uniform_api v4.0.0`

- [ ] **Step 7: Commit**

```bash
git -C ../bk-sops add gcloud/open_plugins config/default.py config/urls_custom.py \
  gcloud/tests/open_plugins/test_catalog_views.py
git -C ../bk-sops commit -m "feat(open_plugins): 新增开放插件目录接口骨架 --story=133649781"
```

---

### Task 3: 标准运维执行网关、幂等与独立 worker

**Files:**
- Modify: `../bk-sops/gcloud/open_plugins/models.py`
- Create: `../bk-sops/gcloud/open_plugins/tasks.py`
- Create: `../bk-sops/gcloud/open_plugins/services/execution.py`
- Create: `../bk-sops/gcloud/open_plugins/services/context.py`
- Create: `../bk-sops/gcloud/open_plugins/services/callbacks.py`
- Modify: `../bk-sops/gcloud/open_plugins/views.py`
- Modify: `../bk-sops/gcloud/taskflow3/celery/settings.py`
- Modify: `../bk-sops/gcloud/taskflow3/celery/tasks.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_execution_gateway.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_callback_bridge.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_context_fallback.py`

- [ ] **Step 1: 写执行网关失败测试**

覆盖：

- `POST /open-plugin-runs` 幂等创建
- `GET /open-plugin-runs/status?task_tag=...` 查询
- `GET /open-plugin-runs/{run_id}` 归属校验
- 回调桥接到 BKFlow 时透传 `callback_url` / `callback_token`

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest ../bk-sops/gcloud/tests/open_plugins/test_execution_gateway.py -v`
- `pytest ../bk-sops/gcloud/tests/open_plugins/test_callback_bridge.py -v`

Expected: FAIL，提示 execute/status/callback 尚未实现

- [ ] **Step 3: 落表 `OpenPluginRun`**

在 `models.py` 中定义最小字段：

```python
class OpenPluginRun(models.Model):
    plugin_id = models.CharField(max_length=128, db_index=True)
    plugin_version = models.CharField(max_length=64)
    client_request_id = models.CharField(max_length=128, unique=True)
    open_plugin_run_id = models.CharField(max_length=64, unique=True, db_index=True)
    callback_url = models.URLField(max_length=512)
    callback_token = models.CharField(max_length=512)
    run_status = models.CharField(max_length=32, db_index=True)
    caller_app_code = models.CharField(max_length=64, db_index=True)
    trigger_payload = models.JSONField(default=dict)
    outputs = models.JSONField(default=dict)
    error_message = models.TextField(blank=True, default="")
```

同时新增迁移文件。

- [ ] **Step 4: 实现执行适配与上下文回退**

在 `services/execution.py` / `services/context.py` 中：

- 统一构造 `open_plugin_run_id`
- 按 `client_request_id` 做幂等命中
- 对 phase-1 来源应用 `default_project_id` 与白名单
- 内置插件直接派发到 `open_plugin_*` 队列
- 第三方插件继续转已有插件服务，不把插件代码装进新 worker

- [ ] **Step 5: 配置独立 worker 队列**

在 `../bk-sops/gcloud/taskflow3/celery/settings.py` 增加：

- `open_plugin_dispatch`
- `open_plugin_polling`
- `open_plugin_callback`

并在 `tasks.py` 中注册对应任务，确保与存量 `task_callback` / `node_auto_retry` 队列隔离。

- [ ] **Step 6: 实现状态查询与回调桥接**

在 `views.py` / `services/callbacks.py` 中补齐：

- `POST /open-plugin-runs`
- `GET /open-plugin-runs/status`
- `GET /open-plugin-runs/{run_id}`
- 对 `callback_url` 做域白名单校验
- 对 `run_id` 查询做接入方归属校验
- 节点已终态时回调按幂等方式吞掉，不产生副作用

- [ ] **Step 7: 跑执行与回调测试**

Run:
- `pytest ../bk-sops/gcloud/tests/open_plugins/test_execution_gateway.py -v`
- `pytest ../bk-sops/gcloud/tests/open_plugins/test_callback_bridge.py -v`
- `pytest ../bk-sops/gcloud/tests/open_plugins/test_context_fallback.py -v`

Expected: PASS，且队列路由落到新 worker 域

- [ ] **Step 8: Commit**

```bash
git -C ../bk-sops add gcloud/open_plugins \
  gcloud/taskflow3/celery/settings.py \
  gcloud/taskflow3/celery/tasks.py \
  gcloud/tests/open_plugins
git -C ../bk-sops commit -m "feat(open_plugins): 新增执行网关与独立 worker 域 --story=133649781"
```

---

### Task 4: BKFlow 开放插件目录索引与空间开放状态

**Files:**
- Modify: `bkflow/plugin/models.py`
- Create: `bkflow/plugin/services/open_plugin_catalog.py`
- Modify: `bkflow/space/configs.py`
- Modify: `bkflow/space/serializers.py`
- Modify: `bkflow/space/views.py`
- Modify: `bkflow/space/urls.py`
- Create: `bkflow/plugin/migrations/0002_open_plugin_catalog_index.py`
- Test: `tests/interface/space/test_space_views.py`
- Test: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: 写空间治理失败测试**

覆盖：

- 新来源导入后空间内默认 `enabled = false`
- 空间管理员可以单个开启、批量全开
- “一键全开”只作用于当前已发现插件
- 后续目录新增插件仍默认关闭

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest tests/interface/space/test_space_views.py -v`
- `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`

Expected: FAIL，提示缺模型或接口

- [ ] **Step 3: 扩展 `UniformApiConfig` 声明开放来源**

在 `bkflow/space/configs.py` 中继续复用 `UniformApiConfig`，为每个来源补齐：

- `source_key`
- `display_name`
- `category_api`
- `list_meta_api`
- `detail_meta_api`
- `callback_domain_allow_list`

不要新建第二套来源配置体系。

- [ ] **Step 4: 新增目录索引与空间开放状态模型**

在 `bkflow/plugin/models.py` 增加：

- `OpenPluginCatalogIndex`
- `SpaceOpenPluginAvailability`

约束：

- 目录索引以 `(space_id, source_key, plugin_id)` 去重
- 空间开放状态以 `(space_id, source_key, plugin_id)` 去重
- 当前阶段只按 `plugin_id` 粒度治理，不按 `(plugin_id, version)` 治理

- [ ] **Step 5: 实现目录同步服务**

在 `bkflow/plugin/services/open_plugin_catalog.py` 中实现：

- 从远端拉分类 / 列表 / 详情
- 刷新本地索引
- 首次导入时为当前空间批量写 `enabled=false`
- 存量迁移命令写 `enabled=true`

- [ ] **Step 6: 暴露空间级管理接口**

在 `bkflow/space/views.py` / `serializers.py` / `urls.py` 增加：

- 获取当前空间开放插件列表
- 切换单个插件 `enabled`
- 对当前可见插件执行“一键全开”

权限沿用空间管理员 / 超管控制。

- [ ] **Step 7: 跑空间治理测试**

Run:
- `pytest tests/interface/space/test_space_views.py -v`
- `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`

Expected: PASS，本地索引与空间开关行为稳定

- [ ] **Step 8: Commit**

```bash
git add bkflow/plugin/models.py \
  bkflow/plugin/services/open_plugin_catalog.py \
  bkflow/space/configs.py \
  bkflow/space/serializers.py \
  bkflow/space/views.py \
  bkflow/space/urls.py \
  bkflow/plugin/migrations/0002_open_plugin_catalog_index.py \
  tests/interface/space/test_space_views.py \
  tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 新增开放插件目录索引与空间治理 --story=133649781"
```

---

### Task 5: BKFlow 插件查询、APIGW 接口与服务端校验

**Files:**
- Modify: `bkflow/apigw/serializers/plugin.py`
- Modify: `bkflow/apigw/views/list_plugins.py`
- Modify: `bkflow/apigw/views/get_plugin_schema.py`
- Modify: `bkflow/plugin/services/plugin_schema_service.py`
- Modify: `bkflow/template/serializers/template.py`
- Modify: `bkflow/apigw/views/create_task.py`
- Modify: `bkflow/apigw/management/commands/data/api-resources.yml`
- Modify: `bkflow/apigw/docs/zh/list_plugins.md`
- Modify: `bkflow/apigw/docs/zh/get_plugin_schema.md`
- Modify: `bkflow/apigw/docs/zh/create_task.md`
- Modify: `bkflow/apigw/docs/apigw-docs.zip`
- Test: `tests/interface/apigw/test_list_plugins.py`
- Test: `tests/interface/apigw/test_get_plugin_schema.py`

- [ ] **Step 1: 写 APIGW 查询失败测试**

覆盖：

- `list_plugins` 能返回开放插件来源字段
- `get_plugin_schema` 支持 `plugin_version`
- 服务端在模板保存 / 任务创建时校验当前空间是否仍开放该插件

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest tests/interface/apigw/test_list_plugins.py -v`
- `pytest tests/interface/apigw/test_get_plugin_schema.py -v`

Expected: FAIL，提示参数、返回结构或治理拦截缺失

- [ ] **Step 3: 扩展插件查询序列化器与 service**

在 `bkflow/apigw/serializers/plugin.py` 和 `bkflow/plugin/services/plugin_schema_service.py` 中：

- 允许查询参数显式带 `plugin_source` / `plugin_id` / `plugin_version`
- 对开放插件优先走本地目录索引，不每次直连远端
- 只有 `enabled=true` 且目录仍存在的插件才对外可见

- [ ] **Step 4: 在模板保存和任务创建入口增加治理校验**

在 `bkflow/template/serializers/template.py` 与 `bkflow/apigw/views/create_task.py` 中复用同一校验函数：

- 旧模板如果引用已关闭插件，可查看但不能继续新建任务
- 新建任务必须命中当前空间开放状态

- [ ] **Step 5: 同步 APIGW 资源与文档**

按照 `.ai/rules/apigw-resource-sync.mdc`：

- 更新 `bkflow/apigw/management/commands/data/api-resources.yml`
- 更新 `bkflow/apigw/docs/zh/list_plugins.md`
- 更新 `bkflow/apigw/docs/zh/get_plugin_schema.md`
- 更新 `bkflow/apigw/docs/zh/create_task.md`
- 运行 `bash scripts/apigw_docs.sh`

- [ ] **Step 6: 跑查询与 APIGW 测试**

Run:
- `pytest tests/interface/apigw/test_list_plugins.py -v`
- `pytest tests/interface/apigw/test_get_plugin_schema.py -v`
- `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`

Expected: PASS，且 `apigw-docs.zip` 已刷新

- [ ] **Step 7: Commit**

```bash
git add bkflow/apigw/serializers/plugin.py \
  bkflow/apigw/views/list_plugins.py \
  bkflow/apigw/views/get_plugin_schema.py \
  bkflow/apigw/views/create_task.py \
  bkflow/plugin/services/plugin_schema_service.py \
  bkflow/template/serializers/template.py \
  bkflow/apigw/management/commands/data/api-resources.yml \
  bkflow/apigw/docs/zh/list_plugins.md \
  bkflow/apigw/docs/zh/get_plugin_schema.md \
  bkflow/apigw/docs/zh/create_task.md \
  bkflow/apigw/docs/apigw-docs.zip \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py
git commit -m "feat(apigw): 接入开放插件查询与服务端治理校验 --story=133649781"
```

---

### Task 6: BKFlow 运行时回调鉴权、ID 映射与取消语义

**Files:**
- Modify: `bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py`
- Modify: `bkflow/task/models.py`
- Modify: `bkflow/apigw/views/operate_task_node.py`
- Create: `bkflow/plugin/services/open_plugin_snapshot.py`
- Test: `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py`
- Test: `tests/interface/apigw/test_operate_task_node.py`

- [ ] **Step 1: 写回调安全失败测试**

覆盖：

- execute 时生成并落表 `client_request_id` / `open_plugin_run_id` 映射
- `callback_token` 过期、签名错误、重放请求被拒绝
- 节点已终态时回调幂等吞掉
- 节点取消/强制失败时向标准运维发取消请求

- [ ] **Step 2: 运行失败测试**

Run:
- `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`
- `pytest tests/interface/apigw/test_operate_task_node.py -v`

Expected: FAIL，提示映射落表或 token 校验缺失

- [ ] **Step 3: 落表回调映射**

在 `bkflow/task/models.py` 或 `bkflow/plugin/models.py` 新增 `OpenPluginRunCallbackRef`，至少保存：

- `task_id`
- `node_id`
- `client_request_id`
- `open_plugin_run_id`
- `callback_token_digest`
- `callback_expire_at`
- `plugin_source`
- `plugin_id`
- `plugin_version`

- [ ] **Step 4: 完成 v4 execute / polling / callback 逻辑**

在 `v4_0_0.py` 中：

- 生成 `client_request_id`
- 生成动态 `callback_url`
- 签发 `callback_token`
- 将 `plugin_version`、`client_request_id`、`callback_*` 透传到标准运维
- 轮询时以 `open_plugin_run_id` 为 task tag

- [ ] **Step 5: 在 `operate_task_node` 增加 callback 校验分支**

仅对开放插件回调路径启用：

- token 验签
- TTL 校验
- `task_id/node_id/client_request_id` 匹配校验
- 节点终态幂等处理

- [ ] **Step 6: 加入取消语义**

在包装器 schedule / task action 逻辑中约定：

- BKFlow 节点被取消或强制失败时，调用标准运维取消接口
- 标准运维取消失败只记日志，不影响 BKFlow 节点进入终态

- [ ] **Step 7: 跑运行时测试**

Run:
- `pytest tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py -v`
- `pytest tests/interface/apigw/test_operate_task_node.py -v`

Expected: PASS，回调安全与取消语义闭环

- [ ] **Step 8: Commit**

```bash
git add bkflow/pipeline_plugins/components/collections/uniform_api/v4_0_0.py \
  bkflow/task/models.py \
  bkflow/apigw/views/operate_task_node.py \
  bkflow/plugin/services/open_plugin_snapshot.py \
  tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py \
  tests/interface/apigw/test_operate_task_node.py
git commit -m "feat(task): 补齐开放插件回调鉴权与运行映射 --story=133649781"
```

---

### Task 7: 插件快照、版本状态与迁移脚本

**Files:**
- Modify: `bkflow/template/models.py`
- Modify: `bkflow/task/models.py`
- Modify: `bkflow/template/serializers/template.py`
- Modify: `bkflow/plugin/services/open_plugin_snapshot.py`
- Create: `bkflow/plugin/management/commands/backfill_open_plugin_snapshots.py`
- Test: `tests/interface/plugin/services/test_plugin_schema_service.py`

- [ ] **Step 1: 写快照与失效版本失败测试**

覆盖：

- 模板节点持久化 `plugin_reference_snapshot`
- 任务执行快照持久化 `plugin_schema_snapshot`
- 失效版本仍可回看，不可继续新建任务
- 历史快照按 `schema_protocol_version` 只读渲染，不强升级

- [ ] **Step 2: 运行失败测试**

Run: `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`
Expected: FAIL，提示缺少快照字段或状态计算

- [ ] **Step 3: 在模板与任务快照中写入统一插件快照**

快照至少包括：

```python
{
    "plugin_reference_snapshot": {
        "plugin_type": "uniform_api",
        "plugin_source": "sops_open_plugins",
        "plugin_id": "open_plugin_001",
        "plugin_code": "job_execute_task",
        "plugin_version": "1.2.0",
        "wrapper_version": "v4.0.0",
    },
    "plugin_schema_snapshot": {
        "schema_protocol_version": "bkflow_plugin_schema_snapshot/v1",
        "inputs": [...],
        "outputs": [...],
    },
}
```

- [ ] **Step 4: 实现版本状态判定**

在 `open_plugin_snapshot.py` 中收敛为两态：

- `available`
- `unavailable`

旧版本若不再出现在目录索引中，模板编辑页只读展示并引导切换到可用版本。

- [ ] **Step 5: 编写存量回填命令**

实现 `backfill_open_plugin_snapshots`：

- 为历史模板补 `plugin_version`
- 为历史模板和任务补 `plugin_schema_snapshot`
- 不自动升级到最新版本

- [ ] **Step 6: 跑快照测试**

Run:
- `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`
- `python manage.py backfill_open_plugin_snapshots --dry-run`

Expected: PASS，且 dry-run 输出补齐数量统计

- [ ] **Step 7: Commit**

```bash
git add bkflow/template/models.py \
  bkflow/task/models.py \
  bkflow/template/serializers/template.py \
  bkflow/plugin/services/open_plugin_snapshot.py \
  bkflow/plugin/management/commands/backfill_open_plugin_snapshots.py \
  tests/interface/plugin/services/test_plugin_schema_service.py
git commit -m "feat(plugin): 新增开放插件快照与版本迁移能力 --story=133649781"
```

---

### Task 8: 统计维度、联调验证与收尾

**Files:**
- Modify: `bkflow/statistics/models.py`
- Modify: `docs/specs/2026-04-20-sops-open-plugin-integration-design.md`（仅在实现偏差需回写时）
- Test: `tests/interface/apigw/test_list_plugins.py`
- Test: `tests/interface/apigw/test_get_plugin_schema.py`
- Test: `tests/plugins/components/collections/uniform_api_test/test_v4_0_0.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_catalog_views.py`
- Test: `../bk-sops/gcloud/tests/open_plugins/test_execution_gateway.py`

- [ ] **Step 1: 扩展统计维度**

在 `bkflow/statistics/models.py` 中评估并补齐 `(plugin_source, plugin_code, plugin_version)` 维度，避免来源与版本混淆。

- [ ] **Step 2: 准备联调数据**

在标准运维侧准备：

- 一个内置开放插件
- 一个第三方开放插件
- 一个白名单内且不依赖用户级凭证的插件版本集合

在 BKFlow 侧准备：

- 一个新空间
- 一个存量迁移空间

- [ ] **Step 3: 跑 BKFlow 侧回归**

Run:
- `pytest tests/plugins/uniform_api/test_uniform_api_client.py -v`
- `pytest tests/plugins/components/collections/uniform_api_test -v`
- `pytest tests/interface/plugin/services/test_plugin_schema_service.py -v`
- `pytest tests/interface/space/test_space_views.py -v`
- `pytest tests/interface/apigw/test_list_plugins.py tests/interface/apigw/test_get_plugin_schema.py tests/interface/apigw/test_operate_task_node.py -v`

Expected: PASS

- [ ] **Step 4: 跑标准运维侧回归**

Run:
- `pytest ../bk-sops/gcloud/tests/open_plugins -v`
- `pytest ../bk-sops/gcloud/tests/external_plugins -v`
- `pytest ../bk-sops/gcloud/tests/taskflow3/tasks/test_task_callback.py -v`

Expected: PASS，且现有任务 worker 行为不受影响

- [ ] **Step 5: 做端到端联调**

联调路径至少覆盖：

1. BKFlow 新空间接入来源，默认插件关闭
2. 空间管理员开启当前目录中的某个标准运维插件
3. 模板保存并生成任务
4. 同步模式执行成功
5. 轮询模式执行成功
6. 回调模式执行成功
7. 关闭插件后旧模板不可新建任务

- [ ] **Step 6: Commit**

```bash
git add bkflow/statistics/models.py
git commit -m "feat(statistics): 扩展开放插件统计维度 --story=133649781"
```

---

## MVP Cut

按依赖关系，推荐把实现分成以下上线批次：

- **P0**
  - Task 1
  - Task 2
  - Task 3
  - Task 4
  - Task 5
  - Task 6
- **P1**
  - Task 7
  - Task 8 的统计维度扩展
- **P2**
  - 更强的失效版本升级辅助 UI
  - 更细粒度的版本级开放治理
  - 用户级凭证透传与代理身份模型

**MVP = P0 全量 + P1 中的快照回填命令，不包含版本升级辅助 UI。**

---

## Verification Checklist

- BKFlow `uniform_api v1/v2/v3` 测试保持通过
- BKFlow 新增或修改的 `bkflow/apigw/**/*.py` 已同步更新：
  - `bkflow/apigw/management/commands/data/api-resources.yml`
  - `bkflow/apigw/docs/zh/*.md`
  - `bkflow/apigw/docs/apigw-docs.zip`
- 标准运维开放插件 worker 与存量 task worker 已隔离
- 标准运维第三方插件仍走既有插件服务，不要求 open worker 安装插件代码包
- 历史模板/任务能回看失效插件版本配置
- 空间关闭开放插件后，存量模板不可继续新建任务
- `callback_token` 通过签名、TTL、映射三层校验

---

## Notes For Executor

- 先在 BKFlow 仓库完成 Task 1、Task 4、Task 5、Task 6、Task 7，再切到标准运维仓库做 Task 2、Task 3，最后回 BKFlow 做联调收尾，会更容易调试。但提交仍应按任务边界拆分，不要混成一个大 commit。
- 任何修改 `bkflow/apigw/` 的任务，必须同步执行 `bash scripts/apigw_docs.sh`。
- 若标准运维开放层实现后发现 `default_project_id` 无法覆盖某类插件，请不要临时扩充 BKFlow 运行时上下文；先把该插件加入一期不开放白名单，并回写 spec。
