# 流程卡住治理：统一开关与旧配置迁移

本说明适用于 BKFlow 接入统一开关之后的版本。统一开关只管理应用侧配置，不改变运行时依赖，也不需要新增依赖或数据库迁移。各环境变量在进程启动时读取，修改后需重启实际消费的 worker、web/API 进程；定时周期变化还需重启 beat。

标准运维（bk-sops）使用同一套统一入口。BKFlow 按自身已接入的能力做了裁剪：扫描器只有 3 种（无动静兜底扫描、丢失类型扫描、回调扫描），没有补充检测；执行保护没有同步节点推进检查点；另外保留了数据清理、恢复范围（space/tenant）和自动暂停等独立配置。下面只列 BKFlow 实际生效的入口。

## 统一入口

| 环境变量 | 可选值 | 作用 |
| --- | --- | --- |
| `BKAPP_DIAGNOSTICS_DETECTION_ENABLED` | `0` / `1` | 关闭 / 开启定时检测；配合 `BKAPP_DIAGNOSTICS_SCANNERS` 选择范围 |
| `BKAPP_PIPELINE_FENCE_MODE` | `off` / `observe` / `enforce` | 防重复检查：关闭 / 只观察 / 开始拦截，默认关闭 |
| `BKAPP_DIAGNOSTICS_RECOVERY_POLICY` | `off` / `preview` / `auto` | 周期恢复：停止新增 / 只预演 / 在允许范围内自动重放 |
| `BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED` | `0` / `1` | 禁止 / 允许控制台人工写操作，默认关闭 |
| `BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE` | `off` / `alerts` / `full` | 关闭事件和告警 / 只输出告警 / 再记录诊断事件，默认关闭 |

**关键规则：新入口未设置时继续逐项读取旧环境变量，升级前后行为不变。** 不要把"没设置新入口"等同于"新入口设为 `off`"。新旧同时设置且含义冲突时，进程启动会抛出 `ValueError` 并点名冲突的旧变量，不会静默开关能力。

新布尔值支持 `1/0`、`true/false`、`yes/no`、`on/off`；模式值和扫描器名称会校验，非法值启动报错。旧配置独立使用时保留原解析方式（字符串 `"0"` 不会当成真值）。

## 检测范围

`BKAPP_DIAGNOSTICS_DETECTION_ENABLED=1` 默认启用 BKFlow 的全部 3 种定时扫描。需要分批开启时，额外设置 `BKAPP_DIAGNOSTICS_SCANNERS`：

| 值 | 扫描内容 |
| --- | --- |
| `window` | 无动静兜底扫描（`BKAPP_DIAGNOSTICS_WINDOW_SCAN_ENABLED`） |
| `signature` | 丢失类型扫描（`BKAPP_DIAGNOSTICS_SIGNATURE_SCAN_ENABLED`） |
| `callback` | 回调扫描（`BKAPP_DIAGNOSTICS_CALLBACK_SCAN_ENABLED`） |

多个值用逗号分隔；不设置表示 3 种全选，显式空字符串表示全不选。只配置 `SCANNERS` 而不配置检测总开关会在启动时报错。

统一检测入口生效后，旧的取样静默扫描（`BKAPP_DIAGNOSTICS_SCAN_ENABLED`）不再执行，它的旧值兼容为窗口扫描：旧 `SCAN_ENABLED=1` 与新配置选中 `window` 可同时存在；若新配置关闭检测或排除了 `window`，则报冲突。旧 `SCAN_ENABLED=0` 不会否决窗口扫描开启。未设置统一入口时，BKFlow 仍保留取样扫描路径，四种检测开关（含取样）完全按旧值独立生效。

检测总开关为 `0` 时，上述定时任务在获取 Redis 锁或查询数据库前返回；周期任务仍保留注册。检测总开关不影响人工诊断、事件记录、告警、历史数据清理或已有案例的恢复，也不控制执行保护。

## 防重复检查与恢复

| 新配置 | 兼容到原有配置 |
| --- | --- |
| `FENCE_MODE=off` | `PIPELINE_FENCE_EMIT_ENABLED=0`、`PIPELINE_FENCE_ENFORCE=0` |
| `FENCE_MODE=observe` | `PIPELINE_FENCE_EMIT_ENABLED=1`、`PIPELINE_FENCE_ENFORCE=0` |
| `FENCE_MODE=enforce` | `PIPELINE_FENCE_EMIT_ENABLED=1`、`PIPELINE_FENCE_ENFORCE=1` |
| `RECOVERY_POLICY=off` | `RECOVERY_ENABLED=0`、`RECOVERY_MODE=preview` |
| `RECOVERY_POLICY=preview` | `RECOVERY_ENABLED=1`、`RECOVERY_MODE=preview` |
| `RECOVERY_POLICY=auto` | `RECOVERY_ENABLED=1`、`RECOVERY_MODE=apply` |

新恢复入口使用 `RECOVERY_POLICY`，避免重新解释旧 `BKAPP_DIAGNOSTICS_RECOVERY_MODE=preview/apply`。新 `auto` 对应引擎的 `apply`，旧变量仍只接受其原有语义。

自动重放仍受 `BKAPP_DIAGNOSTICS_AUTO_REPLAY_TYPES`、`BKAPP_DIAGNOSTICS_RECOVERY_SCOPES`（单租户填 space_id，多租户填 `tenant_id:space_id`，空白名单拒绝所有自动重放）、限次、每轮上限和自动暂停规则约束。执行类和轮询类恢复还要求 `FENCE_MODE=enforce`。`RECOVERY_POLICY=auto` 不会开启人工写操作；要停止所有新增恢复，应同时设置 `RECOVERY_POLICY=off` 和 `BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED=0`，并移除或同步旧 `APPLY_ENABLED`。

人工写操作使用 `BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED`，旧名 `BKAPP_DIAGNOSTICS_APPLY_ENABLED` 继续兼容：新名未设置时沿用旧值；同时设置时须一致，否则启动报错。引擎仍读取同一个人工操作配置，权限检查、预检查和操作审计不变。

检测总开关和恢复模式都不会关闭防重复检查。需要暂停检测或新增恢复时，保留 `FENCE_MODE=enforce`，避免迟到的原 worker 绕过已经建立的推进权保护。

## 事件与告警

`BKAPP_DIAGNOSTICS_OBSERVABILITY_MODE` 统一事件记录和告警日志：

| 模式 | 诊断事件落库（`EVENT_ENABLED`） | 诊断告警日志（`ALERT_ENABLED`） |
| --- | --- | --- |
| `off` | 关闭 | 关闭 |
| `alerts` | 关闭 | 开启 |
| `full` | 开启 | 开启 |

此模式只控制原有 `EVENT_ENABLED` / `ALERT_ENABLED`，不控制案例、恢复记录、操作审计或指标。`full` 会增加事件表写入，正常观察可用 `alerts`。**不配置新入口及对应旧变量时，事件和告警均保持关闭。**

## 未被统一入口管理的配置

以下 BKFlow 配置保持原样、不受 5 个统一入口派生，继续按原有环境变量独立解析：

- 历史数据清理：`BKAPP_DIAGNOSTICS_CLEANUP_ENABLED`、`BKAPP_DIAGNOSTICS_CLEANUP_CRON`、三种保留天数。
- 恢复范围与限流：`BKAPP_DIAGNOSTICS_RECOVERY_SCOPES`、`AUTO_REPLAY_TYPES`、`MAX_ATTEMPTS`、`MAX_PER_ROUND`、`BREAKER_WINDOW_SECONDS`、`BREAKER_THRESHOLD`、`SETTLE_SECONDS`、`RECOVERY_BATCH`。
- 各扫描器阈值、档位、周期与排除码：`WINDOW_TIERS`、`WINDOW_MAX_ROOTS`、`SIGNATURE_FAST/SLOW_THRESHOLD_SECONDS`、`POLL_EXCLUDE_CODES`、`CALLBACK_CONFIRM_SECONDS`、`SCAN_CRON`、`SIGNATURE_SCAN_CRON`、`CALLBACK_SCAN_INTERVAL`、`RECOVERY_CRON`、`STALL_THRESHOLD_SECONDS`、`SCAN_BATCH`、`SCAN_MAX_SILENT_SECONDS`、`SECOND_CONFIRM_SECONDS`。

## 从旧配置迁移

每组配置可以独立迁移。建议在同一次配置变更中移除被替代的旧变量，避免后续切换模式时留下冲突：

| 新入口 | 对应旧变量（以下均带 `BKAPP_` 前缀） |
| --- | --- |
| `DIAGNOSTICS_DETECTION_ENABLED` + 可选 `DIAGNOSTICS_SCANNERS` | `DIAGNOSTICS_SCAN_ENABLED`、`DIAGNOSTICS_WINDOW_SCAN_ENABLED`、`DIAGNOSTICS_SIGNATURE_SCAN_ENABLED`、`DIAGNOSTICS_CALLBACK_SCAN_ENABLED` |
| `PIPELINE_FENCE_MODE` | `PIPELINE_FENCE_EMIT_ENABLED`、`PIPELINE_FENCE_ENFORCE` |
| `DIAGNOSTICS_RECOVERY_POLICY` | `DIAGNOSTICS_RECOVERY_ENABLED`、`DIAGNOSTICS_RECOVERY_MODE` |
| `DIAGNOSTICS_MANUAL_APPLY_ENABLED` | `DIAGNOSTICS_APPLY_ENABLED` |
| `DIAGNOSTICS_OBSERVABILITY_MODE` | `DIAGNOSTICS_EVENT_ENABLED`、`DIAGNOSTICS_ALERT_ENABLED` |

例如，迁移后打开检测总开关，但仍保留旧 `WINDOW_SCAN_ENABLED=0`，会因默认选中了 `window` 而报错；应删除旧变量，或用 `SCANNERS` 明确排除 `window`。新 `RECOVERY_POLICY=off` 的内部兼容值是 `RECOVERY_ENABLED=0`、`RECOVERY_MODE=preview`；若保留旧 `RECOVERY_MODE=apply` 会报冲突，不要在回退时只新增一个 `off` 而保留不一致的旧值。

完成代码升级并核对所有相关进程版本后，可先按以下配置只开回调检测和恢复预演：

```text
BKAPP_DIAGNOSTICS_DETECTION_ENABLED=1
BKAPP_DIAGNOSTICS_SCANNERS=callback
BKAPP_PIPELINE_FENCE_MODE=observe
BKAPP_DIAGNOSTICS_RECOVERY_POLICY=preview
BKAPP_DIAGNOSTICS_MANUAL_APPLY_ENABLED=0
```

扩大检测范围时调整 `SCANNERS`，移除该变量会选择全部 3 种扫描。启用自动恢复前，再验证防重复检查、恢复范围和类型，并切换到 `enforce` / `auto`。

若回退到尚不支持新入口的应用版本，须先恢复匹配的旧环境变量；旧版本会忽略这些新变量，新 `off` 下继续回查的能力无法由旧 `RECOVERY_ENABLED=0` 表达。
