# BKAIDev Harness P0 本地验收

- 日期：2026-09-01
- 实现分支：`feat/a2flow-harness-p0`
- 可还原基线：`feat/a2flow@52f62d89`
- Spec：`docs/specs/2026-09-01-bkaidev-a2flow-harness-design.md`
- Plan：`docs/plans/2026-09-01-bkaidev-a2flow-harness-p0.md`
- Spike：`docs/reviews/2026-09-01-bkaidev-harness-p0-spike.md`
- TAPD：`136729554`

## 最终状态

```text
LOCAL_IMPLEMENTATION_COMPLETE
P0_RELEASE_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
SPIKE_EXTERNAL_EVIDENCE_BLOCKED
```

本地 Django 实现、契约测试和 30 条 Golden Cases 已跑通。不能把「本地测试通过」写成「BKAIDev 已联调」或「P0 可发布」。

## P0 Gate 清单

| 门禁项 | 本地结论 | 证据 |
|---|---|---|
| 一个逻辑 MCP 已配置 | 未验证 | 只有配置契约，见 Spike Task 9 附录 |
| 恰好四个 P0 Tool 可见 | 未验证 | 仓库已有四个 prefixed APIGW operation；BKAIDev 可见性无真机清单 |
| 可信 app/user/space/scope/environment | 本地通过 | Task 4/8/10 自动化测试；无 BKAIDev JWT 抓包 |
| 30 条 Golden Cases | 本地通过 | `tests/interface/harness/test_golden_cases.py` 执行 30/30 |
| BKAIDev on-demand Schema 对比 | 未执行 | `SPIKE_EXTERNAL_EVIDENCE_BLOCKED` |
| 10-20 个试点能力精确版本/哈希 | 未执行 | 无试点空间 |
| 安全不变式计数器全 0 | 本地通过 | `tests/interface/harness/test_security_boundaries.py` |
| P0 未发布模板、未建任务、未真实执行 | 本地通过 | Golden Cases 与安全测试断言；无线上执行证据 |

任一未验证项保持门禁未完成，不降低标准。

## 实现提交

| Task | SHA | Message |
|---|---|---|
| 1 | `487a4e41` | docs(harness): 固化 BKAIDev P0 接入探针 --story=136729554 |
| 2 | `4032f224` | feat(harness): 新增 P0 运行与版本模型 --story=136729554 |
| 3 | `6c5d6528` | feat(harness): 建立版本哈希状态机与幂等基础 --story=136729554 |
| 4 | `e857e550` | feat(harness): 接入可信上下文与空间鉴权 --story=136729554 |
| 5 | `ed738418` | feat(harness): 增加能力检索投影与精确 Schema 绑定 --story=136729554 |
| 6 | `8585f54f` | feat(harness): 增加确定性流程校验与不可变修订 --story=136729554 |
| 7 | `bdae2608` | feat(harness): 复用 a2flow 创建服务并限制为草稿 --story=136729554 |
| 8 | `068a4018` | feat(harness): 暴露四个 P0 控制接口 --story=136729554 |
| 9 | `70980f87` | docs(apigw): 同步 Harness P0 资源与 BKAIDev 配置 --story=136729554 |
| 10 | 本提交 | test(harness): 建立 P0 Golden Cases 与发布门禁 --story=136729554 |

四个 MCP-visible Tool 与 APIGW operation：

| MCP-visible Tool | APIGW operationId |
|---|---|
| search_workflow_capabilities | harness_search_workflow_capabilities |
| get_plugin_schema | harness_get_plugin_schema |
| validate_workflow | harness_validate_workflow |
| create_workflow_draft | harness_create_workflow_draft |

Harness migrations：`bkflow/harness/migrations/0001_initial.py`、`0002_harnessidempotencyrecord_status.py`。`makemigrations harness --check` 无新变更。

## Golden Cases

Fixture：`tests/fixtures/harness/golden_cases.yaml`，`version: p0-v1`。

| Group | Count | 本地结果 |
|---|---:|---|
| positive_selection | 8 | PASS |
| ambiguous_requires_clarification | 6 | PASS |
| zero_candidate | 4 | PASS |
| schema_validation_error | 4 | PASS |
| schema_drift | 3 | PASS |
| idempotent_draft_retry | 3 | PASS |
| forged_identity_rejected | 2 | PASS |
| **Total** | **30** | 无 xfail |

## 安全不变式

```text
cross_space_leak = 0
secret_or_token_exposure = 0
duplicate_drafts = 0
silent_schema_drift = 0
published_templates = 0
created_tasks = 0
real_executions = 0
```

本地测试断言上述计数器保持 0。Interface 模块未安装 task app，因此 `created_tasks` 用「未创建模板发布快照 / 未进入 PUBLISHED 或 EXECUTING」代理，而不是查询 `TaskInstance`。

## 本地命令与结果

聚焦回归：

```bash
pytest tests/interface/harness \
  tests/interface/apigw/test_harness_p0.py \
  tests/interface/apigw/test_harness_resource_contract.py \
  tests/interface/apigw/test_list_plugins.py \
  tests/interface/apigw/test_get_plugin_schema.py \
  tests/interface/apigw/test_validate_a2flow.py \
  tests/interface/apigw/test_create_template_with_a2flow.py \
  tests/interface/plugin/services/test_plugin_schema_service.py -v --no-cov
```

结果：`188 passed in 213.23s`。含 30 条 Golden Cases，无 P0 验收 xfail。

风格与框架：

| 命令 | 结果 |
|---|---|
| `flake8 bkflow/harness bkflow/template/services bkflow/apigw/serializers/harness bkflow/apigw/views/harness tests/interface/harness` | exit 0 |
| `python manage.py check` | exit 0；既有 warning `label.Label.label_scope` JSONField default |
| `python manage.py makemigrations harness --check` | exit 0，`No changes detected in app 'harness'` |
| `python manage.py makemigrations --check` | exit 1，既有 drift：`space` name choices、`template` operate_type。**不是本次 Harness 变更。** |
| `git diff --check`（本次相关路径） | exit 0 |
| `black --check`（系统 black，未走 pre-commit 版本） | 会重排大量已提交文件，未采用 |
| `pre-commit run black`（Task 10 新增/修改文件） | 已按仓库 hook 格式化 |

## 实现偏差

1. 空检索需要 recovery guidance。`search_workflow_capabilities` 在无候选时返回 `next_actions=[{action: revise_query}]`。这满足 Task 10 `zero_candidate` 预期，不改变搜索排序或鉴权。
2. Task 10 提交除计划列出的测试/文档外，包含 `bkflow/harness/services/projection.py` 与 `facade.py` 的上述 `next_actions` 变更。
3. Golden Cases 使用 pinned registry snapshot 和转换/模板创建 mock，不访问真实插件中心或 BKAIDev。

未修改 approved spec。

## 明确未验证

- BKAIDev SaaS 单智能体、MCP 连接、四 Tool 可见性
- 嵌套 JSON、五轮 `run_id` 保持、刷新/压缩/瞬时错误
- BKAIDev 真机 JWT 与 space/scope 绑定
- Schema 体积、超时、Token 窗口
- P0 Prompt 边界的线上执行
- baseline vs on-demand Schema 对比的实测正确率/延迟/Token
- 10-20 个试点能力
- `harness_enabled=true` 的非生产试点空间配置

## P1-P4 未实现确认

P0 没有实现：联邦 Knowledge Router、`search_workflow_knowledge`、单步/全局调试、Token Broker、`sdk_xxx`、审批、发布、任务创建、真实执行、反馈闭环、第 16 个 Tool `start_generation_run`、第二个 Agent 或自主 MCP 循环。

## 解除门禁前必须补的外部证据

1. 完成 Spike SP-01 至 SP-07，更新 Spike 文档并关闭 `SPIKE_EXTERNAL_EVIDENCE_BLOCKED`。
2. 按 Task 9 契约在 BKAIDev 配置一个 SaaS 单智能体和 `BKFlow Workflow Harness MCP`，钉住 Agent Release。
3. 用同一 Release 跑 Golden Cases 子集，记录 baseline/candidate Schema 对比。
4. 在非生产试点空间解析 10-20 个能力，记录查询、版本、`schema_hash`、正/歧义/空/漂移/幂等草稿，不含 Token 或凭证明文。
