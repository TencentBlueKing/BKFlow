# BKAIDev a2flow Harness P3 本地验证记录

## 证据身份与裁决

```text
branch = ai/a2flow-harness-p3
verified_predecessor_sha = 195b589d7a34a040751cae2f0f0e6673dde3002b
verified_at = 2026-09-06 Asia/Shanghai
local_gate = P3_LOCAL_GATE_PASSED
external_gate = P3_RELEASE_EXECUTION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

本记录验证的是上述精确 Task 10 基线加 Task 11 候选差异。候选树尚未提交，不能在文件内容中嵌入其最终 SHA；提交后的精确 SHA 由 Git 历史承载。本地 test double 证据不等同于真实 BKAIDev、审批方、Engine、Token 或生产数据库验收。

## 开关与本地边界

| 配置 | 本地冻结值 | 说明 |
| --- | --- | --- |
| `harness_publish_enabled` | 默认 `false`，测试空间显式 `true` | 仅用于确定性本地发布用例 |
| `harness_execution_enabled` | 默认 `false`，测试空间显式 `true` | 仅用于确定性本地执行用例 |
| `harness_global_real_enabled` | `false` | P3 不启用 global real |
| approval verifier | in-memory test double | 验证 action/digest/identity/expiry；不是 live receipt |
| runtime adapter | deterministic test double | 记录 create/start/read/control 次数；不是 live Engine |

## 48 条可执行 Golden Cases

Fixture `tests/fixtures/harness/release_execution_cases.yaml` 固定 48 行。每行声明完整 trusted context、前序 Revision、草稿指纹、服务端策略、approval 模式、Engine 序列、真实 Tool/payload、Envelope code、Run/Execution 后置状态、Evidence 序列、TokenLease 结果、外部动作次数和 forbidden markers。动态值只替换固定 `$...` 占位符。

| 分类 | 数量 | 实际入口 |
| --- | ---: | --- |
| `prepare_and_manifest` | 8 | `prepare_release_with_context` |
| `approval_binding_and_expiry` | 6 | publish/start public service |
| `publish_idempotency_and_drift` | 6 | `publish_workflow_with_context` |
| `create_start_recovery` | 8 | `start_workflow_execution_with_context` |
| `execution_readback` | 5 | `get_workflow_execution_with_context` |
| `postcondition_false_success` | 5 | execution GET + fixed postcondition policy |
| `task_controls` | 4 | control + readback public services |
| `node_controls` | 4 | control + mapping/version readback |
| `secret_and_cross_space_denial` | 2 | start public service，副作用前拒绝 |
| **合计** | **48** | **20 release + 26 execution + 2 security** |

Runner 按 operation 分派统一 public service，case id 仅作 pytest 标签；20/26/2 三分区互斥且并集精确为 48。断言覆盖 Manifest/Approval/Publication/Execution/Idempotency/Evidence/Lease 等 durable state，并以 adapter 的实际调用记录计算 publish/create/start/read/control mutation。所有 48 行都会扫描响应和 Harness 聚合持久化字段中的 forbidden markers；其中 `secret-shaped-runtime-input-denied-before-persistence` 实际注入 runtime secret sentinel，额外的 downstream-failure/replay 用例实际注入下游 secret-bearing 异常并检查响应、数据库与日志。其余 marker 是每行统一执行的回归哨兵，不表示每种 secret 形态都在每一行被注入。legacy `permission.Token.token` 明文兼容表明确不在 P3 零明文结论范围内。

崩溃/恢复覆盖包括 publication anchor 回滚、已发布 response-loss 精确读回、create barrier 后、create ack 后 task_ref 落库前、task_ref 落库后 start 前、start ack 不确定、control barrier 后和 control dispatch 后。可安全恢复的行从 durable anchor 收敛且不重复下游 mutation；无法判定 create/control 是否已送达的行保持 `*_UNCERTAIN` 或 `*_DISPATCHING` 并要求人工协调，不把不确定状态伪装为成功。

## 当前本地证据

```bash
python -m pytest \
  tests/interface/harness/release/test_golden_cases.py \
  tests/interface/harness/execution/test_golden_cases.py \
  tests/interface/harness/execution/test_secret_non_disclosure.py \
  -q --strict-markers --disable-warnings --no-cov
```

结果：**68 passed**，且已包含在下述完整门禁中。其中 48 行逐行进入真实 P3 public service；其余用例验证结构、14 Tool 合同、声明 anti-drift、分区、runner 禁止按 case id 分支、完整 service trace、恢复中间态以及 secret-bearing 下游失败的幂等恢复。

完整本地门禁命令：

```bash
make harness-p3-gate \
  PYTHON=/path/to/repository-python \
  'PYTEST=/path/to/repository-python -m pytest'
```

该目标依次运行 Django system check、Harness migration drift check、APIGW docs zip 完整性检查、P0-P3 Harness/permission/template debug/APIGW、Template release、Task creator characterization、48-case/14-Tool/secret gate，最后执行 `git diff --check`。Makefile 可覆写 `PYTHON`/`PYTEST`，不加载个人 `.env`，并启用 `--strict-markers`。

2026-09-06 完整结果：**1931 passed, 8 skipped in 534.57s**，命令退出码为 0。8 个 skip 均为 SQLite 无法证明双连接行锁或生产数据库并发语义；串行幂等路径已覆盖，但这些 skip 不构成 MySQL/PostgreSQL 验收证据。Django system check 仅报告仓库既有的 `label.Label.label_scope` JSONField default warning 和测试初始化中的 naive Token datetime warning；Harness migration 无漂移，APIGW docs zip 完整，最终 `git diff --check` 通过。

## 外部证据缺口

| 边界 | 状态 | 仍需证据 |
| --- | --- | --- |
| BKAIDev 单 MCP、14 Tool 挂载与可信身份读回 | `BLOCKED / NOT_RUN_EXTERNAL` | live Tool discovery 与 platform/app/actor/space/scope/env readback |
| live approval receipt | `BLOCKED / NOT_RUN_EXTERNAL` | provider signature、claims、expiry、replay 与 publish/start/control 分离审批 |
| 非生产 publish | `BLOCKED / NOT_RUN_EXTERNAL` | Template version、snapshot、operation record、response-loss readback |
| live Engine create/start/read/control | `BLOCKED / NOT_RUN_EXTERNAL` | task ref、state、node mapping/version、控制结果与刷新恢复 |
| false-success Postcondition | `BLOCKED / NOT_RUN_EXTERNAL` | Engine FINISHED 但业务谓词失败的真实 Evidence |
| Token/credential boundary | `BLOCKED / NOT_RUN_EXTERNAL` | 平台应用代用户授权、最小租约、撤销与不向 Agent 暴露明文 |
| MySQL/PostgreSQL | `BLOCKED / NOT_RUN_EXTERNAL` | migration、行锁顺序与并发 crash recovery |

因此外部裁决保持 **`P3_RELEASE_EXECUTION_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`**，所有 P3 rollout flags 必须维持默认关闭，直到上述证据逐项补齐。
