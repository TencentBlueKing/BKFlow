# 存量调试结果回填

`backfill_debug_snapshots` 将仍可核实的旧调试结果保存到 `debug_snapshot`，使之后的画布编辑不会改变这份结果列表。默认只预览，需显式传入 `--apply` 才会写入。

## 执行位置与范围

在 **Interface 模块**使用目标环境的配置执行。Interface 通过空间绑定的 Engine 接口读取历史任务，不直接访问 Engine 数据库。先完成包含本命令及重置保护的 Interface 滚动发布，再执行回填；旧实例不具备相同的重置并发保护。

本命令不需要新增数据库字段。每条记录单独处理，不启动或重跑任务，不改变当前节点状态、Mock 设置、变量及 `active_debug_snapshot`。

先按一个空间或少量模板预览，例如：

```bash
python manage.py backfill_debug_snapshots --space-id 245 --limit 100 --dry-run
python manage.py backfill_debug_snapshots --template-id 2339 --template-id 2694
```

空间和模板参数可重复传入，同时提供时取交集。以上 ID 仅为示例，执行时替换成目标范围。预览会读取本地记录及历史任务，但不会写入。

核对报告后，对同一范围实际回填：

```bash
python manage.py backfill_debug_snapshots --space-id 245 --limit 100 --apply
```

需要扫描全部记录时显式使用 `--all`，不能和空间或模板筛选同时使用。默认每批读取 100 条上下文，本次最多扫描 1000 条；`--batch-size` 取值 1 至 1000，`--limit` 控制本次总量。历史任务和节点按需逐个读取，同一上下文内复用任务信息；每条成功记录仅更新一次快照。

## 恢复规则

- 只处理空闲、`debug_snapshot` 为 SQL NULL、仍有已结束节点结果的上下文。有快照、空对象重置标记、JSON null、运行中任务及不存在的模板都跳过。
- 状态、输入输出、耗时、错误、日志引用和已有运行时间沿用 `DebugNodeState`。不会用 Engine 的当前结果覆盖旧节点结果。
- 每个已执行节点通过自己的 `log_ref` 找历史任务，核对空间、模板、DEBUG 类型和节点映射。活动名称及类型来自任务的原始节点快照；网关来自任务流程快照；执行模式来自该任务的 Mock 记录。执行人使用对应任务的 `executor`，缺失时为空，不推测节点级操作人。
- 有完整全局任务时沿用其流程顺序，单步结果只替换对应节点。多个全局任务的结构必须一致；只有单步历史时，只能可靠恢复单个结果，多个节点缺少完整流程顺序就整条跳过。流程排序使用模板节点 ID，避免运行时随机 ID 改变并行分支顺序。
- 全局历史中的节点状态必须仍然存在；画布后来新增且未执行的节点不会加入旧快照。删除的节点状态、缺少任务引用的同步 Mock/网关单步，不补造历史，也不进行部分回填。
- **保留已有 `debug_config_hash`、`debug_node_name` 比较基准，不重新计算或回填。** Engine 会清洗、截断节点名称，回填展示的是其保留的历史名称，无法保证与当时草稿文字完全一致。没有比较基准的存量节点继续按 `config_changed=false` 处理；已有基准仍正常比较。下一次实际调试会建立新基准。
- 历史读取在数据库事务外。写入时锁定上下文及节点，重新核对全部字段；期间有新调试、重置或节点变化则跳过。重复执行不会覆盖已回填结果。

## 查看报告与续跑

每条记录输出一行 JSON，包含上下文 `id`、`space_id`、`template_id`、`outcome`，以及节点数或原因。最后一行是汇总。报告不包含节点名称、输入输出或接口异常正文。

| outcome | 含义 |
| --- | --- |
| `ready` | 当前预览可恢复，尚未写入 |
| `applied` | 已成功回填 |
| `skipped` | 不符合条件或缺少可靠历史，原数据保留 |
| `error` | 历史接口读取失败或 Engine 配置不可用，原数据保留 |

常见原因：`snapshot_exists_or_reset` 已有快照或已重置；`context_active` 正在运行；`no_results` 没有可恢复结果；`missing_log_ref` 缺少任务引用；`missing_node_state` 历史节点状态已丢失；`ambiguous_order` 无法确认流程顺序；`invalid_node_mapping` 节点映射不一致；`missing_mock_history` 缺少实际执行模式；`task_identity_mismatch` 任务归属或类型不匹配；`concurrent_change` 读取期间记录发生变化。

有 `error` 时仍会继续处理后续记录并输出汇总，最终以非零状态退出。排查 Engine 路由或历史接口后，按失败的模板 ID 重试；不可恢复的历史继续保留原状，重新调试后自动生成新快照。

汇总中的 `counts.ready / scanned` 可用于查看本次扫描记录的可恢复比例，`reasons` 给出跳过及错误分类。`has_more=true` 时，用 `next_after_id` 作为下一批的 `--after-id`，保持其他范围参数一致：

```bash
python manage.py backfill_debug_snapshots --space-id 245 --after-id 1200 --limit 100 --dry-run
```

`next_after_id` 是本轮已扫描位置，可能包含失败或跳过记录；续跑不会自动重试游标之前的记录。**预览后正式执行同一批时，使用预览前的游标，不能直接使用预览输出的新游标。** 预览结果只代表读取时的可恢复性，实际写入还会再次校验。

## 修复已有快照的空输入

旧版本在同步引擎结果时遗漏了输入参数，可能出现节点已有执行结果但 `debug_snapshot.nodes[].inputs` 为 `{}` 的情况。修复版会在真实调试节点成功或失败时保存引擎返回的实际输入，包括引擎已做的脱敏处理。尚未完成的节点仍可能没有输入；不经过引擎的本地 Mock 不生成真实输入，也不会沿用上一轮参数。

已有快照不会因为发布或读取 `debug_context` 自动修复。待 Interface 完成滚动发布后，在同一模块使用 `--repair-inputs` 先预览、再写入。例如，修复空间 205 下的模板 2512：

```bash
python manage.py backfill_debug_snapshots --space-id 205 --template-id 2512 --repair-inputs --dry-run
python manage.py backfill_debug_snapshots --space-id 205 --template-id 2512 --repair-inputs --apply
```

此模式只修复已有快照，未生成快照的存量记录需要先按前面的普通回填方式生成，再执行输入修复。范围筛选、分页和默认预览规则不变；汇总的 `operation` 为 `repair_inputs`，每条记录的 `nodes` 表示本次可补充输入的节点数。

- 只处理空闲上下文中，输入为 `{}`、已成功或失败且有历史任务引用的活动或子画布节点。已有非空输入、未执行节点、网关、本地 Mock、已重置和缺少快照的记录保持原样。
- 按快照自己的 `log_ref` 查询历史任务，核对空间、模板、DEBUG 类型、节点映射及运行版本。只接受同一版本、同一状态的实际执行输入；不从当前草稿渲染或推测，不补写旧版兜底版本 `v1` 对应的记录。
- 仅修改快照内目标节点的 `inputs`，保留节点顺序、名称、状态、输出、耗时、日志引用和配置比较基准；不改变当前节点控制状态，不启动或重跑任务。
- 同一上下文的候选节点全部核实后才写入。历史读取失败、版本不匹配，或者读取期间发生新调试、重置、快照变化时整条跳过或报错，不部分覆盖。写入前会锁定并重新核对上下文，重复执行不会覆盖已修复输入。

输入修复的额外原因：`snapshot_missing_or_reset` 缺少快照或已重置；`no_missing_inputs` 没有符合条件的空输入；`no_execution_inputs` 引擎同版本输入本来就为空；`node_version_mismatch` 运行版本不一致；`node_state_mismatch` 节点状态不一致；`missing_execution_inputs` 引擎未返回合法输入对象。`missing_log_ref` 也包括缺少可核实的运行版本。
