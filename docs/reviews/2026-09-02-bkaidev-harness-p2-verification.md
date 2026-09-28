# BKAIDev a2flow Harness P2 本地验证记录

## 结论与证据身份

```text
branch = ai/a2flow-harness-p2
verified_predecessor_sha = e31e9ba824313551ffd8546305a307165643bed8
local_gate = P2_LOCAL_GATE_PASSED
real_step_gate = P2_REAL_STEP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE
```

本记录验证的是上述精确 Task 9 基线加 Golden 证据真实性 review-fix 候选差异。候选提交无法在自身内容中嵌入自己的 Git SHA，否则会产生自哈希悖论；最终提交 SHA 应与本记录一并交付，并通过该提交的精确文件 diff 复核。`PASS_LOCAL` 只代表本地仓库行为，不代表 BKAIDev 挂载、真实 Engine、真实平台 Token、审批回执、Artifact 服务或生产数据库验收。

## 冻结开关与运行模式

| 配置 | 本地冻结值/要求 | 说明 |
| --- | --- | --- |
| `harness_debug_enabled` | 默认 `false`；Mock 灰度空间显式设为 `true` | `get_debug_session` 在关闭时仅投影持久化 Session/Evidence，其他调试 Tool 拒绝 |
| `harness_real_step_enabled` | 默认 `false` | 只构成 real-step 第一层服务端策略门禁 |
| `approval_mode` | `deny_real` | 无真实可验证 approval receipt，缺失/伪造/过期均 fail closed |
| `token_issue_mode` | `deny_real` for external rollout | 本地 Broker/Lease 可测，但没有平台应用代用户签发 Token 的线上证据 |
| `global execution_mode` | `mock` only | P2 不允许 global real |
| `async_mode` | `fast_ack_and_poll` | `run_debug` 快速返回，Agent 后续调用 `get_debug_session` |

## 40 条 Golden Cases

Fixture `tests/fixtures/harness/debug_cases.yaml` 固定为 schema v2、40 条。每条都声明完整可信上下文、差异化 setup facts、前序 Revision、草稿指纹关系、真实 Tool 与 payload 模板、Envelope code、Run/Session 状态变化、Evidence 事件、TokenLease 结果、外部变更次数和禁止明文标记。动态请求值只允许 `$session_id/$plan_hash/$run_id/$revision_id` 四个固定占位符；`${safe}` 等业务变量不会被解释为占位符。

| 分类 | 数量 |
| --- | ---: |
| `step_mock_success_failure` | 8 |
| `step_dependency_blocked` | 5 |
| `global_mock_lifecycle` | 5 |
| `session_lock_conflict` | 5 |
| `reset_and_control` | 4 |
| `terminate_and_recovery` | 4 |
| `plan_or_fingerprint_drift` | 3 |
| `token_lifecycle` | 3 |
| `forged_or_expired_approval` | 3 |
| **合计** | **40** |

Runner 要求 case id 与 handler registry 精确相等。40 行均从 fixture 物化请求并实际调用 `start/run/get/control` Facade 或 Token Broker，同时逐项比对运行时可信上下文、Revision latest/superseded 关系与 sequence/validation、草稿指纹 exact/drifted 关系、实际 Tool/payload 和数据库后置状态；它不是 YAML 自洽校验。独立 anti-drift 用例分别篡改 context、Revision、fingerprint 和 request 声明，均会打破 Golden 合同。覆盖包括两个差异化纯 Mock 输出、不同依赖拓扑、gateway approval+lease、本 Session 的 global 收敛、第二个 validated Run 的同 Template 冲突、控制重放、终止前撤权、草稿/Revision 漂移以及缺失、伪造和过期审批。伪造/过期 approval provider 是确定性 test double，并非真实外部回执验收；Engine 与资源校验外部边界也由 test double 代替，因此这些用例仍是本地服务证据。

Contract `1.2.0` 在同一门禁中固定为 9 个累计 Tool；`1.0.0` 的 4 Tool 和 `1.1.0` 的 5 Tool 兼容断言包含在 Harness 全量测试中。

## Secret 与不确定故障门禁

`test_secret_non_disclosure.py` 运行三类独立故障注入：

1. 直接调用 Token Broker，在 Token 已签发、TokenLease 落库前失败：legacy Token 与 Lease 同事务回滚，重试后只保留一个最终 Token/Lease；同一测试另走真实 `get_debug_session` 与 `control_debug_session` Tool Envelope。`run_debug` real-step 在签发前必须已有 live Lease，因此该签发故障不是由 Tool 触发。
2. DebugService/Engine 已确认、Session 状态落库失败：预提交 Session barrier 保留，same-key 和 new-key 重试均不重复 create/start。
3. 单步 Adapter domain result 带入唯一敏感 sentinel，idempotency completion 前失败：domain/Evidence 回滚，barrier 保留，same-key 和 new-key 均不重复 Adapter mutation。

扫描面包括 Tool response、HarnessRun/Revision/Session/TokenLease/Idempotency/Evidence 序列化、DebugContext/DebugNodeState/TemplateSnapshot、INFO 及以上日志和安全异常文本。断言范围必须准确：P2 Harness/TokenLease/Evidence/API 不保存或返回 Token 明文；既有 legacy `permission.Token` 表因兼容协议仍保存 Token 明文，且旧 `apply_token` 响应仍返回明文，故明确排除在零明文扫描结论之外。本地门禁没有把这一兼容事实错误表述为“全 BKFlow 零明文”。

## 精确命令与结果

命令在隔离 worktree 内使用仓库 Python 3.9 虚拟环境执行；`.env` 仅由调用方在命令外加载，Makefile 不写入个人路径或私有环境文件。

```bash
python -m pytest \
  tests/interface/harness/debug/test_golden_cases.py \
  tests/interface/harness/debug/test_secret_non_disclosure.py \
  -q --disable-warnings --no-cov
```

结果：**50 passed in 33.01s**，其中 40 条为逐行真实服务场景，3 条为结构/工具集/Make gate 合同，4 条为声明 anti-drift，3 条为 fault-injection secret 测试。

```bash
make harness-p2-gate \
  PYTHON=/path/to/repository-python \
  'PYTEST=/path/to/repository-python -m pytest'
```

最终严格门禁结果：**1244 passed, 8 skipped in 131.83s**，启用 `--strict-markers`，无 xfail。该目标依次运行：

- `python manage.py check`；
- `python manage.py makemigrations harness --check --dry-run`；
- `unzip -t bkflow/apigw/docs/apigw-docs.zip`；
- Harness P0/P1/P2、permission token、完整 Template Debug、P0/P1/P2 APIGW 与资源/文档一致性测试。

`manage.py check` 退出码为 0，保留既有 `label.Label.label_scope` JSONField callable-default warning；本地初始化还出现既有 `Token.expired_time` naive datetime runtime warning。Harness migration 检查为 `No changes detected in app 'harness'`。APIGW zip 完整性检查无错误。

提交前还执行：

```bash
python manage.py makemigrations harness --check
git diff --check
pre-commit run --files <review-fix 精确文件>
```

这些命令的最终结果必须与提交 SHA 一并交付；若任一失败，本记录的本地通过结论失效。

## SQLite 跳过项

8 个 skip 全部来自继承门禁，没有 P2 Task 9 新增 skip：

| 边界 | 数量 | SQLite 未证明内容 |
| --- | ---: | --- |
| public draft security two-connection | 1 | 公开草稿并发的真实行锁 |
| idempotency two-connection | 2 | 多连接 ownership/retry 锁语义 |
| validator concurrency | 5 | whole-run `select_for_update` 串行化 |
| **合计** | **8** | MySQL/PostgreSQL 真实并发语义仍待外部门禁 |

## 外部证据缺口

| 外部边界 | 当前状态 | 仍需证据 |
| --- | --- | --- |
| BKAIDev 单 MCP、9 Tool 挂载与 Agent Release readback | `NOT_RUN_EXTERNAL / BLOCKED` | 实际 Tool discovery、可信 app/actor/space/scope/env 读回 |
| 真实 Engine step/global/poll/terminate | `NOT_RUN_EXTERNAL / BLOCKED` | 低风险节点 create/start/status/revoke trace 与 task readback |
| 平台应用代用户 Token 签发与撤销 | `NOT_RUN_EXTERNAL / BLOCKED` | 真实平台方身份、Token issuer、TTL/renew/revoke readback；不得向 Agent 暴露 Token |
| approval receipt 验证 | `NOT_RUN_EXTERNAL / BLOCKED` | 可信 issuer/signature/replay/claims/expiry 验证与拒绝 trace |
| Artifact writer/readback | `NOT_RUN_EXTERNAL / BLOCKED` | 大结果脱敏写入、opaque ref 和授权读取闭环 |
| MySQL/PostgreSQL | `NOT_RUN_EXTERNAL / BLOCKED` | migration、nullable unique、锁序、barrier/Token 并发执行 |

## 发布裁决

本地 Mock P2 的唯一诚实结论是 **`P2_LOCAL_GATE_PASSED`**。它允许在 `harness_debug_enabled=true` 的受控空间继续 Mock 灰度，但不自动授权 real step。

真实单步仍缺 BKAIDev approval receipt、平台 Token、真实低风险节点、撤销及 readback 证据，因此结论必须保持 **`P2_REAL_STEP_GATE_BLOCKED_BY_EXTERNAL_EVIDENCE`**。
