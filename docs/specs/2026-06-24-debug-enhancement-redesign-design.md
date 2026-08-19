# BKFlow 流程调试能力增强设计（重设计）

## 背景

BKFlow 当前的"调试"能力实质上只有一种形态：**Mock 任务**。

- 通过 `create_method="MOCK"` 创建一个真实的 `TaskInstance`，配套写入 `TaskMockData`（节点级 mock 输出）。
- 模板侧用 `TemplateMockData`（每节点可复用的 mock 预设）+ `TemplateMockScheme`（UI 上勾选哪些节点 mock）维护可复用的 mock 方案。
- 运行时由插件基类 `BKFlowBaseService` 在 `execute`/`schedule` 中判断 `is_mock`（任务级）∧ `is_mock_node`（节点级），命中则走 `mock_execute`，**不调用真实插件逻辑，直接把预设输出写入节点输出**，再由 bamboo-engine 按 `source_act/source_key` 把输出绑定到下游全局变量。

这套机制能跑通"整条流程用 mock 数据走一遍"，但缺少调试场景真正需要的能力：

- 没有**全局调试**入口（带用户输入参数、从零重置所有节点状态后整体运行）。
- 没有**单步调试**（只跑某个依赖已满足的节点）。
- 没有**统一的调试上下文/快照**（全局变量、各节点状态分散，无法增量更新与查看）。
- 编辑节点/连线后，**哪些节点的调试结果失效**没有提示，用户不知道需要重跑哪些。
- Mock 配置（模板侧）与运行态（任务侧）模型割裂，难以统一管理。

本次重设计以**调试上下文（DebugContext）为中心**，在尽量复用现有引擎短路机制的前提下，提供全局调试、单步调试、统一上下文、变更影响提示、mock 单步、即时终止等能力；并对标 Dify / Coze 等工作流平台的调试体验，补充手动输入单节点试运行、变量直编、mock 失败注入、节点可观测、调试历史与输入复用等能力。**本期范围为后端优先（backend-first）**，前端交互不在本 spec 内细化。

## 设计目标与非目标

### 目标（对应需求）

| 编号 | 需求 | 落地章节 |
|---|---|---|
| req1 | 全局调试：用户输入参数，从零重置所有节点状态后整体运行 | [全局调试](#全局调试-req1) |
| req2 | 单步调试：无输入依赖或依赖已在全局上下文满足的节点可单独执行 | [单步调试](#单步调试与手动输入试运行-req2-req9) |
| req3 | 统一调试上下文/快照：全局与单步调试都更新同一份调试状态 | [统一调试上下文](#统一调试上下文-req3) |
| req4 | 节点/连线变更时，按节点类型规则告知前端哪些节点状态需重置 | [变更重置规则](#变更重置规则req4) |
| req5 | 单步支持 mock：直接设置节点输出，并同步到调试上下文全局变量 | [Mock 单步与输出回写](#mock-单步与输出回写-req5) |
| req6 | 兼容旧 mock 能力，旧 mock 数据可继续使用 | [旧 Mock 兼容](#旧-mock-兼容-req6) |
| req7 | 调试期间禁止修改节点配置 | [并发与一致性](#并发与一致性) |
| req8 | 支持即时终止调试，运行中节点也能终止 | [终止调试](#终止调试-req8) |
| req9 | 手动输入的单节点试运行：直接填入节点输入、绕过依赖检查单独执行 | [单步调试与手动输入试运行](#单步调试与手动输入试运行-req2-req9) |
| req10 | 直接编辑调试上下文中的全局变量，不重跑上游即可测试下游 | [编辑调试上下文变量](#编辑调试上下文变量-req10) |
| req11 | mock 失败/异常注入：mock 节点可标记为失败并带错误信息，驱动失败分支/异常处理/重试 | [Mock 单步输出回写与失败注入](#mock-单步输出回写与失败注入-req5-req11) |
| req12 | 调试态节点可观测：记录耗时、错误详情、调用日志引用、网关分支求值结果 | [调试态可观测](#调试态可观测-req12) |
| req13 | 调试运行历史：查看模板的历次调试运行记录 | [调试历史与输入复用](#调试历史与输入复用-req13-req14) |
| req14 | 输入参数保存/复用，并暴露模板必填输入常量元数据 | [调试历史与输入复用](#调试历史与输入复用-req13-req14) |

> req9–req14 为对标 Dify / Coze 调试能力后补充的需求（手动单节点测试、变量直编、失败注入、节点可观测、调试历史、输入复用），与 req1–req8 同期实现。

### 非目标（本期不做）

- 前端页面与交互的具体实现。
- 子流程（`SubProcess`）节点内部下钻 mock —— 现有引擎短路只对继承 `BKFlowBaseService` 的插件节点生效，子流程不走该基类。本期 **mock 对象限定为 `ServiceActivity` 插件节点**。
- 网关/控制节点的 mock —— 控制节点不产出输出，没有"mock 输出"语义；它们只作为 req4 重置规则的传播对象。
- 生产任务回放、自动化回归、智能诊断等高级能力（属于更早一版方案，已剥离，本期不纳入）。

## 核心概念

| 概念 | 说明 |
|---|---|
| **DebugContext** | 每个模板唯一的调试上下文，跨用户共享。保存当前调试全局变量、树指纹、调试状态、并发锁、最近一次 DEBUG 任务引用。 |
| **DebugNodeState** | 每模板每节点一条，记录该节点的执行模式（real/mock）、mock 预设输出、最近一次运行的输入/输出快照、运行状态、配置指纹。 |
| **DEBUG 任务** | 全局调试时创建的真实 `TaskInstance(create_method="DEBUG")`，复用 bamboo-engine 执行；在任务列表中默认隐藏。 |
| **引擎短路机制（复用 + 小幅扩展）** | `BKFlowBaseService.execute/schedule` 中 `is_mock ∧ is_mock_node` 命中走 `mock_execute`，注入预设输出而不调真实插件。成功 mock 完全复用现有逻辑（零改动）；失败注入（req11）需对 `mock_execute` 做一处向后兼容扩展（读取失败标记 → 设置 `ex_data` 并返回 False）。 |

## 总体架构

```
                ┌────────────────────────────────────────────┐
   前端编辑/调试  │              Debug API 层                    │
 ───────────────▶│  global_run / step_run / node_mock /         │
                 │  reset / reset_impact / terminate / context  │
                 └───────────────┬─────────────────────────────┘
                                 │
                 ┌───────────────▼─────────────────────────────┐
                 │            DebugService（编排）               │
                 │  - 抢锁/状态机管理                            │
                 │  - 物化临时 TaskMockData                      │
                 │  - 输出→全局变量回写（source_act/source_key） │
                 │  - 依赖图构建 + reset 影响计算                │
                 └──────┬───────────────────────┬──────────────┘
                        │                        │
          ┌─────────────▼──────────┐   ┌─────────▼───────────────┐
          │ DebugContext /          │   │ bamboo_engine_api        │
          │ DebugNodeState（落库）   │   │ run/pause/revoke/        │
          │ EncryptedJsonField      │   │ forced_fail_activity     │
          └─────────────────────────┘   └──────────────────────────┘
```

DebugService 是唯一编排入口：管理 `DebugContext` 状态机与并发锁，决定调用引擎（全局调试 / 终止）还是直接执行/回写（单步 / mock 单步），并维护统一上下文。

## 数据模型

### DebugContext（每模板唯一）

| 字段 | 类型 | 说明 |
|---|---|---|
| template_id | IntegerField, unique | 一模板一份调试上下文 |
| space_id | IntegerField, db_index | 空间隔离与鉴权 |
| global_vars | EncryptedJsonField | 当前调试全局变量 `{key: value}` |
| tree_fingerprint | JSONField | 各节点 `config_hash` + 拓扑/连线/常量指纹，供 `reset_impact` diff |
| status | CharField | `idle` / `running` / `terminating` |
| active_task_id | IntegerField, null | 当前/最近一次 DEBUG 任务实例 id |
| last_inputs | EncryptedJsonField | 最近一次全局调试的输入参数，供下次预填（req14） |
| locked_by | CharField, blank | 持锁用户（共享并发） |
| locked_at | DateTimeField, null | 持锁时间 |
| (CommonModel) | | creator / create_at / update_at / is_deleted |

### DebugNodeState（每模板每节点一份）

| 字段 | 类型 | 说明 |
|---|---|---|
| debug_context | ForeignKey(DebugContext) | 所属上下文 |
| node_id | CharField | 节点 id |
| execution_mode | CharField | `real` / `mock`，决定调试时该节点是否真跑（默认 `real`，生命周期见下文[execution_mode 生命周期](#execution_mode-生命周期方案-a)） |
| mock_result | CharField | `success` / `fail`（mock 时生效，默认 `success`，req11） |
| mock_outputs | EncryptedJsonField | mock 成功时注入的预设输出（跨 reset 保留） |
| mock_error | CharField | mock 失败时注入的错误信息（req11，跨 reset 保留） |
| status | CharField | `not_run` / `running` / `finished` / `failed` |
| inputs | EncryptedJsonField | 最近一次运行的渲染输入快照（reset 清空） |
| outputs | EncryptedJsonField | 最近一次运行的输出快照（reset 清空） |
| duration_ms | IntegerField, null | 最近一次运行耗时（req12，reset 清空） |
| error_detail | EncryptedJsonField | 最近一次运行的错误详情 `{type, message}`（req12，reset 清空） |
| log_ref | JSONField, null | 引擎引用 `{instance_id, node_id, version}`，供前端用现有任务详情接口拉取该次运行的详情/日志/耗时（req12，reset 清空）；mock 运行为空 |
| config_hash | CharField | 上次成功调试时的节点配置指纹 |
| last_run_at | DateTimeField, null | 最近一次运行时间 |
| | | `unique_together = (debug_context, node_id)` |

> **关键区分**：`mock_result` / `mock_outputs` / `mock_error` 是用户预设（reset 时保留）；`outputs` / `duration_ms` / `error_detail` / `log_ref` 是实际运行结果（reset 时清空）。这呼应 req1（重置只清运行结果与全局变量、保留 mock 配置）与 req6。

### 节点状态机

```
 not_run ──run──► running ──► finished
    ▲                    └──► failed
    │
    └── reset（reset_impact 命中 / 全局重置 / 终止后）  ◄── finished / failed / running
```

`reset` 等价回到 `not_run`：清空运行结果（`inputs / outputs / duration_ms / error_detail / log_ref / status / last_run_at`），**保留 mock 配置（`execution_mode` / `mock_result` / `mock_outputs` / `mock_error`）**。

## 执行流程

### 全局调试（req1）

1. 入参：`{template_id, inputs}`。`inputs` 为模板用户输入类常量（show_type=show / 自定义）的取值。
2. 抢锁：`DebugContext.status` 非 `idle` 时拒绝（见[并发与一致性](#并发与一致性)）。
3. **从零重置**：清空所有 `DebugNodeState` 的运行结果（`status→not_run`、清 inputs/outputs），重置 `global_vars`（以本次 `inputs` 为初始值），**保留各节点 `execution_mode` 与 `mock_outputs`**。
4. **物化临时 mock**：收集所有 `execution_mode=mock` 的节点，生成一份 `TaskMockData`（`{nodes:[...], outputs:{...}}`）挂到本次 DEBUG 任务。
5. 创建 `TaskInstance(create_method="DEBUG")`，调用 `bamboo_engine_api.run_pipeline` 整体运行。引擎正常推进拓扑：mock 节点命中短路注入预设输出，real 节点真实执行；所有节点输出按 `source_act/source_key` 绑定到全局变量。
6. 运行过程中通过引擎状态信号回写 `DebugNodeState`（status/inputs/outputs）与 `DebugContext.global_vars`，保持统一上下文（见 req3）。
7. 运行结束（成功/失败/终止）后 `status→idle`、解锁。

> mock 节点为何能"跳过"：bamboo-engine 不在拓扑层跳过节点，节点照常被调度、状态照常流转、输入照常渲染；只是 `BKFlowBaseService.execute` 在 `is_mock ∧ is_mock_node` 命中时改走 `mock_execute`，注入 `TaskMockData.data["outputs"][node_id]` 而不发起真实调用。需要轮询的插件由 `mock_schedule` 以 2s 间隔直接 finish。

### 单步调试与手动输入试运行（req2 req9）

1. 入参：`{template_id, node_id, mode?: real|mock, mock_outputs?, input_overrides?}`。`mode` 省略时**默认取该节点的 `execution_mode`**；显式传 `mode` 仅影响**本次**运行，**不修改** `execution_mode`（见[配置 vs 运行边界](#mock-配置与运行的边界方案-a)）。
2. **可执行性判定**（仅在未提供 `input_overrides` 时进行）：解析该节点输入引用的全局变量。
   - 普通用户常量恒可用。
   - 由其他节点产出的变量（`component_outputs` 常量）必须已在 `DebugContext.global_vars` 中有值（即其产出节点已被调试过）。
   - 无输入依赖的节点恒可单步。
   - 任一被引用的"产出型变量"缺值 → 不可单步，返回缺失变量及其产出节点提示。
3. **输入来源**：
   - **未传 `input_overrides`（默认）**：从 `DebugContext.global_vars` 水合（hydrate）该节点输入。
   - **传 `input_overrides`（req9 手动输入试运行）**：直接用传入值作为该节点输入，**绕过依赖检查与上下文水合**，用于在上游尚未运行时单独测试某节点（对标 Dify/Coze 的"单节点测试"）。
4. **执行**（两条路径，明确区分）：
   - **real 模式**：用上述输入组装一个**仅含该节点的最小单节点 pipeline**，经 `bamboo_engine_api` 真实运行（复用插件 `execute`/`schedule` 与变量渲染）。
   - **mock 模式**：**不经引擎**，按 `mock_result` 直接产出成功输出或失败（见 [Mock 单步输出回写与失败注入](#mock-单步输出回写与失败注入-req5-req11)）。
5. **回写**：把节点输出/状态写入 `DebugNodeState`，成功时按 `source_act==node_id / source_key` 映射回写 `DebugContext.global_vars`（见 req3）；同时记录耗时/错误/日志引用（见 req12）。real/mock 两条路径共用同一回写逻辑。
6. 单步执行也受并发锁约束（`running` 期间不可并发其它运行/编辑）。

### Mock 单步输出回写与失败注入（req5 req11）

- 单步时 `mode=mock`：按 `mock_result` 分两种结果，**均不发起真实调用**：
  - `success`：采用 `mock_outputs`（请求传入或取 `DebugNodeState.mock_outputs`）作为该节点输出。与 real 模式走**同一套回写逻辑**：写入 `DebugNodeState.outputs`，并按 `source_act/source_key` 同步到 `DebugContext.global_vars`。
  - `fail`（req11 失败注入）：把节点置为 `failed`，写入 `mock_error` 到 `error_detail`，**不回写全局变量**。用于调试失败分支、异常处理节点、自动重试、以及基于节点状态的网关决策。
- 这保证"直接设置节点输出 → 同步到调试上下文全局变量"（req5），同时支持"模拟某节点失败"（req11），下游单步可立即消费成功值或验证失败处理路径。
- `node_mock` 接口设置/更新某节点的 `mock_result` / `mock_outputs` / `mock_error` 并触发回写，而不重跑该节点；**同时把该节点 `execution_mode` 置为 `mock`**（方案 A，见下文）。

> **全局调试中的失败注入**：物化临时 `TaskMockData` 时，把 `mock_result=fail` 的节点信息一并写入；引擎执行到该节点时由扩展后的 `mock_execute` 设置 `ex_data` 并返回 False，使节点真实进入失败态，从而触发引擎原生的失败分支/异常处理流程。这是本设计对引擎侧唯一的小幅扩展（向后兼容：无失败标记时行为与现状完全一致）。

### execution_mode 生命周期（方案 A）

`execution_mode` 是"该节点在调试中是否真跑"的唯一开关（**不是**"有没有设 `mock_outputs`"）。采用方案 A：**配置 mock 输出即进入 mock 模式**，符合"我给它配了 mock，就是要 mock 它"的直觉。写入点收敛为：

| 时机 | 行为 |
|---|---|
| DebugNodeState 初始化（首次进上下文 / 新增节点） | 默认 `real` |
| 旧数据迁移（req6） | `TemplateMockScheme` 勾选过的节点 → 初始 `mock` |
| 调用 `node_mock` 设置输出 | **同时置 `execution_mode=mock`** |
| 调用 `node_mock` 且 `enable=false`（切回真跑） | 置 `execution_mode=real`，**保留** `mock_outputs` / `mock_result` / `mock_error` 作为预设 |

`reset` / `reset_impact` / `step_run` **不改** `execution_mode`。

### Mock 配置与运行的边界（方案 A）

为避免实现期把"配置"与"运行"写混，显式固定两条边界：

1. **配置 vs 运行**：`execution_mode`（及 `mock_*` 预设）是**节点配置**，决定全局调试与默认单步的行为；`step_run.mode` 是**本次运行**的临时选择，不回写配置。例：对一个 `execution_mode=mock` 的节点做一次 `step_run(mode=real)`，只是"这一次真跑一下"，节点对全局调试仍是 mock。
2. **本次 vs 持久**：`step_run` 内联传入的 `mock_outputs` **只作用于本次**运行；要**持久化**预设必须走 `node_mock`。即只有 `node_mock`（及迁移、`reset` 对运行结果的清理）会触达预设/配置字段，`step_run` 永不写 `mock_outputs` / `execution_mode`。

### 是否真跑——判定真值表（方案 A）

| `execution_mode` | 设了 `mock_outputs`? | 全局调试 | 单步（`mode` 省略） | 单步（显式 `mode=real`） |
|---|---|---|---|---|
| `mock` | 是 | mock（注入预设） | mock | **真跑（仅本次，不改配置）** |
| `mock` | 否 | mock（注入空，建议校验提示） | mock（同左） | 真跑（仅本次） |
| `real` | 是（仅留存预设） | **真跑**（预设被忽略） | 真跑 | 真跑 |
| `real` | 否 | 真跑 | 真跑 | 真跑 |

> 结论：在方案 A 下，**经 `node_mock` 设置过 mock 输出的节点默认不会真跑**（全局/单步都走 mock）；只有显式 `node_mock(enable=false)` 切回 real，或单次 `step_run(mode=real)`，才会真执行。

### 编辑调试上下文变量（req10）

- 提供 `POST /debug/context_var` 直接设置 `DebugContext.global_vars[key] = value`，不重跑任何节点。
- 用途：在不重跑昂贵上游节点的前提下，手动改写某个全局变量值，随后单步运行下游节点验证其行为（对标 Dify Variable Inspector 的变量直编、Coze 的"调试时临时改变量值"）。
- 仅在 `status=idle` 时允许（运行中锁定，见[并发与一致性](#并发与一致性)）。
- 编辑属于"手工干预",不影响 `tree_fingerprint`；但下游节点既有运行结果是否过期由用户自行判断，本接口不自动触发 reset。

### 统一调试上下文（req3）

- 全局调试与单步调试都读写**同一份 `DebugContext` + `DebugNodeState`**。
- 全局调试由引擎信号驱动批量更新；单步调试由 DebugService 直接更新。两条路径最终落到同一上下文。
- `GET /debug/context` 是**统一聚合层**：返回合并后的 `global_vars` + 各节点调试态（status、execution_mode、mock_result、可单步性、duration_ms、error_detail、`log_ref`）+ 上下文 `status`/`locked_by`/`last_inputs`。real 节点的 status/耗时可内部聚合 `get_task_states`，节点级重数据由前端凭 `log_ref` 回查任务详情接口（见[可观测数据来源与任务详情接口复用](#可观测数据来源与任务详情接口复用)）。

### 终止调试（req8）

- 入参：`{template_id}`（可选 `node_id` 用于节点级强制失败）。
- 把 `DebugContext.status→terminating`。
- 整体终止：对 `active_task_id` 调 `bamboo_engine_api.revoke_pipeline`。
- 运行中节点强制失败：调 `bamboo_engine_api.forced_fail_activity`。
- 引擎回调后把受影响节点 `status` 落为 `failed`/`reset`，`DebugContext.status→idle` 解锁。

### 调试态可观测（req12）

每次节点运行（全局或单步、real 或 mock）结束时，在 `DebugNodeState` 上记录可观测信息：

- `duration_ms`：节点执行耗时（轻量冗余，便于列表直接展示；详情仍可经 `log_ref` 回查引擎）。
- `error_detail`：失败时的结构化错误 `{type, message}`（real 失败取 `ex_data`；mock 失败取 `mock_error`）。
- `log_ref`：**引擎引用** `{instance_id, node_id, version}`，指向该次运行所在的引擎实例与节点。前端凭它直接复用现有任务详情接口拉取重数据（详情/输入输出/日志/耗时），无需 Debug 侧重复实现：
  - real 运行（全局调试或 real 单步的 mini-pipeline）→ `log_ref` 指向对应引擎实例，可调 `get_node_detail` / `get_node_log` / `get_node_data`。
  - mock 运行 → 不经引擎、无 call log，`log_ref` 为空；输出/错误直接取 `DebugNodeState`。
- **网关分支求值结果**：网关类节点记录本次实际走向的分支（引擎在决策时已产生该信息），供前端展示"为什么走了这条分支"。
- 上述字段均随 `reset` 清空。

> 说明：本节聚焦后端**记录与暴露**可观测数据；前端的失败节点高亮、调用栈/火焰图等可视化不在本期范围（见[未来扩展](#未来扩展非本期)）。

### 可观测数据来源与任务详情接口复用

调试态的"上下文 / 全局变量 / 各节点耗时与日志"分两类来源，**能复用就复用现有任务详情接口，不重复造**：

| 数据 | 全局调试（real 节点） | 单步 real | 单步 / 全局 mock 节点 |
|---|---|---|---|
| 节点状态 + 耗时 | 复用 `get_task_states`（DEBUG `task_id`） | 复用 `get_task_states`（mini 实例） | 取 `DebugNodeState`（不经引擎） |
| 全局变量 | 见下"统一上下文"说明 | 同左 | 取 `DebugContext.global_vars` |
| 节点输入/输出 | 复用 `get_node_detail` / `get_node_data` | 同左（mini 实例） | 取 `DebugNodeState.outputs` |
| 节点日志 | 复用 `get_node_log` | 同左（mini 实例） | 无引擎日志，标记为 mock |

要点：

- **全局调试本身就是真实 `TaskInstance`**，故节点级重数据（详情/输入输出/日志/耗时）**直接复用任务详情那套接口**（凭 DEBUG `task_id` 或 `log_ref` 中的 `instance_id`），Debug 侧不重复实现。
- **三处不能直接复用**，必须由 Debug 侧统一上下文兜底：① 单步结果不在全局 DEBUG 任务实例里（real 单步是独立 mini 实例，由 `log_ref` 定位）；② mock 不经引擎，既无引擎 context 也无 call log；③ 统一 `DebugContext` 是"最近一次全局运行 + 后续单步 + 手工改量"的**合并视图**，没有任何单个实例能代表它，`render_current_constants` 只反映某一个实例的引擎 context，会与合并后的 `global_vars` 发散。
- **结论**：`GET /debug/context` 作为**统一聚合 / 索引层**——返回合并后的 `global_vars` 与各节点调试态（含 `execution_mode`/`mock_result`/可单步性/`status`/`duration_ms`/`error_detail`/`log_ref`）；real 节点的 status/耗时可由 context 内部聚合 `get_task_states`，重数据则由前端凭 `log_ref` 按需回查任务详情接口。前端无需自行合并两套语义。
- **实时拉取范式**：轮询 `GET /debug/context`（轻量、统一）+ 按需用 `log_ref` 调 `get_node_detail` / `get_node_log`（重数据）。

### 调试历史与输入复用（req13 req14）

- **调试历史（req13）**：`GET /debug/history?template_id=` 返回该模板历次全局调试运行（来自保留的 `create_method="DEBUG"` 任务实例）：`task_id`、发起人、开始时间、最终状态、本次输入摘要。受 TTL 清理约束（见[清理](#清理ttl)），仅展示未过期记录。
- **输入复用（req14）**：每次 `global_run` 把本次 `inputs` 写入 `DebugContext.last_inputs`；`GET /debug/context` 一并返回，供前端预填上次输入。
- **必填输入常量元数据（req14）**：`GET /debug/input_schema?template_id=` 从 `pipeline_tree` 的 `constants` 中解析用户输入类常量（show_type=show / 自定义），返回 `{key, name, type, default, required}` 列表，供前端自动生成全局调试的输入表单。

## 变更重置规则（req4）

### 依赖图（两类边）

从 `pipeline_tree` 同时构建两张图，重置传播沿**两张图的并集**做可达性闭包：

| 边类型 | 来源 | 含义 |
|---|---|---|
| 控制流边 | `flows`（source→target） | A 执行完才轮到 B |
| 数据流边 | `constants` 中 `component_outputs` 类型（`source_act`/`source_key`，由 `classify_constants` 解析） | A 的某个输出 → 全局变量 → 被 B 的输入引用 |

### 变更类型 × 节点类型 → 重置规则

核心原则：**一个节点"脏"了，它自己 + 沿并集图可达的所有下游节点的运行结果全部重置**（保守、安全：在不重跑前提下无法断定下游输入未变）。

| 变更 | 脏种子（seed） | 传播 |
|---|---|---|
| 插件节点（`ServiceActivity`）配置变更 | 该节点 | 控制流下游 ∪ 消费其输出变量的节点，取闭包 |
| 网关条件表达式变更 | 网关下游各分支首节点 | 各分支控制流下游闭包 |
| 子流程节点配置变更 | 该子流程节点 | 同插件节点（暂不下钻内部） |
| 新增连线 | 连线 target 节点 | target 控制流下游闭包 |
| 删除连线 | 原 target 节点 | 同上 |
| 新增节点 | 新节点（标记未调试）+ 其下游 | 闭包 |
| 删除节点 | 消费其输出的节点 + 其控制流下游 | 闭包；同时删除该节点自身 DebugNodeState |
| 全局变量（用户自定义常量）值/来源变更 | 引用该变量的所有节点 | 闭包 |
| 仅 UI（坐标/备注）变更 | 无 | 不重置 |

### reset_impact：后端 diff、只读告知

- `DebugContext.tree_fingerprint` 保存上次调试时的树指纹（每节点 `config_hash` + 拓扑/连线/常量指纹）。
- 前端编辑后调 `POST /debug/reset_impact`，后端取当前 draft 快照重算指纹并 diff 出 seed → 沿并集图闭包传播 → 返回 `{reset_node_ids, reasons}`。
- **该接口不修改 `DebugContext`**；真正清除发生在下一次 `global_run` 或显式 `reset`。
- 采用后端 diff 而非前端上报变更：无论前端如何编辑，diff 都能算对，不依赖前端准确上报每一次原子操作。

## 旧 Mock 兼容（req6）

统一到 per-node 模型，同时不破坏引擎短路机制：

- 执行模式与 mock 预设统一收敛到 `DebugNodeState.execution_mode` + `mock_outputs`。
- **运行时物化**：global_run / 带 mock 的 step_run 时，把 `execution_mode=mock` 的节点物化成一份**临时 `TaskMockData`** 挂到 DEBUG 任务，复用 `BKFlowBaseService` 短路。成功 mock 引擎侧零改动；失败 mock（req11）需对 `mock_execute` 做一处向后兼容扩展（无失败标记时行为与现状完全一致）。
- **旧数据复用**：`TemplateMockData`（每节点可复用的 mock 预设）保留，作为填充 `mock_outputs` 的预设来源 —— 用户可一键套用历史 mock 数据，满足"旧 mock 数据可继续使用"。
- `TemplateMockScheme`（旧的"勾选哪些节点 mock"）迁移为 `DebugNodeState.execution_mode` 初始值；旧的"创建 mock 任务"入口在兼容期保留，内部走同一套物化逻辑。

## 并发与一致性

`DebugContext` 每模板一份、跨用户共享，必须处理并发，并据此实现 req7：

- `DebugContext.status ∈ {idle, running, terminating}` + `locked_by` / `locked_at`。
- **运行前抢锁**：`global_run` / `step_run` 前，`status` 非 `idle` 时拒绝并返回"模板正在被 X 调试"。
- **运行中锁编辑（req7）**：`status=running` 时，编辑类接口与 `reset` 一律拒绝。
- `terminate` 置 `status=terminating`；引擎 revoke 回调完成后落回 `idle` 并解锁。
- 全局变量写入语义：同一时刻只有一个运行者，故为**单写者**，无需复杂合并。

## 权限 / 安全 / 清理

### 权限

调试是对模板的操作，复用现有模板维度鉴权（如 `AdminPermission | SpaceSuperuserPermission | ScopePermission`）。所有 Debug 接口校验调用方对 `template_id` 所在空间/模板的权限。

### 安全

- `DebugContext.global_vars`、`DebugNodeState.mock_outputs/inputs/outputs` 可能含敏感数据，统一用 `EncryptedJsonField` 落库（与 `TaskMockData` 现有加密一致）。

### 清理（TTL）

- `global_run` 产生真实 `TaskInstance(create_method="DEBUG")`，会持续累积。
- 任务列表查询默认过滤 `create_method="DEBUG"`，避免污染正常任务列表。
- **保留策略：全部保留 + TTL 定时清理**（如 7 天）。定时任务清理过期 DEBUG 任务实例及其引擎数据；不清理 `DebugContext`（它随模板生命周期存在）。
- 模板删除时级联清理其 `DebugContext`、`DebugNodeState` 及关联 DEBUG 任务。

## API 契约

> 路径为示意，实际前缀按 engine/interface 模块现有路由规范确定。统一返回体遵循 BKFlow 现有响应格式（成功 `200/201`；错误 `Response(exception=True, data={"detail": ...})`）。所有接口均校验调用方对 `template_id` 所在空间/模板的权限。下文 `${key}` 表示全局变量键。

### 调试专用接口（汇总）

| 方法 | 路径 | 请求要点 | 响应要点 | req |
|---|---|---|---|---|
| GET | `/debug/context/` | `template_id` | `global_vars` + 各节点调试态（含可单步性、耗时/错误、`log_ref`）+ `last_inputs` | req3/req12/req14 |
| POST | `/debug/global_run/` | `template_id`, `inputs` | DEBUG `task_id`、上下文状态 | req1 |
| POST | `/debug/step_run/` | `template_id`, `node_id`, `mode`, `mock_*?`, `input_overrides?` | 节点输出/状态、更新后的 `global_vars`、`log_ref` | req2/req5/req9/req11 |
| POST | `/debug/node_mock/` | `template_id`, `node_id`, `enable?`, `mock_result?`, `mock_outputs?`, `mock_error?` | 节点 `execution_mode`、回写后的 `global_vars` | req5/req11 |
| POST | `/debug/context_var/` | `template_id`, `key`, `value` | 更新后的 `global_vars` | req10 |
| POST | `/debug/reset/` | `template_id`（可选 `node_ids`） | `reset_node_ids` | req1 |
| POST | `/debug/reset_impact/` | `template_id`（后端取 draft 快照 diff） | `{reset_node_ids, reasons}`（只读） | req4 |
| POST | `/debug/terminate/` | `template_id`（可选 `node_id`） | 上下文状态 | req8 |
| GET | `/debug/history/` | `template_id`（可选分页） | 历次 DEBUG 运行列表 | req13 |
| GET | `/debug/input_schema/` | `template_id` | 用户输入常量元数据列表 | req14 |

### 请求 / 响应协议（详细）

**GET `/debug/context/`** — 统一上下文（前端实时轮询的主接口）

```json
// 响应 data
{
  "template_id": 123,
  "status": "idle",                 // idle | running | terminating
  "locked_by": "",
  "active_task_id": 456,            // 最近一次全局调试的 DEBUG 任务，可为 null
  "last_inputs": {"${biz_id}": "100"},
  "global_vars": {"${biz_id}": "100", "${job_id}": 789},
  "nodes": [
    {
      "node_id": "node_xxx",
      "node_type": "ServiceActivity",
      "execution_mode": "real",     // real | mock
      "mock_result": null,          // success | fail（execution_mode=mock 时有效）
      "status": "finished",         // not_run | running | finished | failed
      "can_step": true,             // 是否可单步（req2）
      "missing_vars": [],           // 不可单步时缺失的产出型变量
      "duration_ms": 1200,
      "error_detail": null,         // {"type": "...", "message": "..."}
      "log_ref": {"instance_id": "n1a2...", "node_id": "node_xxx", "version": "v1"}
    }
  ]
}
```

**POST `/debug/global_run/`** — 全局调试（req1）

```json
// 请求
{"template_id": 123, "inputs": {"${biz_id}": "100"}}
// 响应 data
{"task_id": 456, "status": "running"}
```

- `409`：`status != idle`，`detail` 含当前 `locked_by`。

**POST `/debug/step_run/`** — 单步 / 手动输入试运行（req2/req5/req9/req11）

```json
// 请求（按 mode 取用对应字段）
{
  "template_id": 123,
  "node_id": "node_xxx",
  "mode": "real",                       // 可选，real | mock；省略则取节点 execution_mode；仅影响本次，不改配置
  "input_overrides": {"${biz_id}": "100"}, // 可选；传则绕过依赖检查（req9）
  "mock_result": "success",             // mode=mock 时：success | fail（req11）
  "mock_outputs": {"data": {"k": "v"}}, // mock_result=success 时的输出（req5）
  "mock_error": ""                       // mock_result=fail 时的错误信息（req11）
}
// 响应 data
{
  "node_id": "node_xxx",
  "status": "finished",                 // finished | failed
  "outputs": {"data": {"k": "v"}},      // 失败时可为 null
  "error_detail": null,
  "updated_global_vars": {"${job_id}": 789},
  "log_ref": {"instance_id": "m9...", "node_id": "node_xxx", "version": "v1"} // mock 运行为 null
}
```

- `400`：未传 `input_overrides` 且依赖不满足 → `detail` + `missing_vars: [{"key", "source_node_id"}]`。
- `409`：`status != idle`。

**POST `/debug/node_mock/`** — 设置节点 mock / 切换执行模式（req5/req11，方案 A）

```json
// 请求：配置 mock（enable 省略或 true）→ 同时置 execution_mode=mock
{"template_id": 123, "node_id": "node_xxx", "enable": true, "mock_result": "success", "mock_outputs": {"k": "v"}, "mock_error": ""}
// 请求：切回真跑 → 置 execution_mode=real，保留 mock_* 预设
{"template_id": 123, "node_id": "node_xxx", "enable": false}
// 响应 data
{"node_id": "node_xxx", "execution_mode": "mock", "updated_global_vars": {"${job_id}": 789}}
```

- `enable` 省略时默认 `true`（设置 mock 输出即进入 mock 模式）。
- `enable=false` 仅切 `execution_mode=real` 并保留预设，不改 `mock_outputs` / `mock_result` / `mock_error`。

**POST `/debug/context_var/`** — 编辑上下文变量（req10）

```json
// 请求
{"template_id": 123, "key": "${biz_id}", "value": "200"}
// 响应 data
{"global_vars": {"${biz_id}": "200"}}
```

- `409`：`status != idle`（运行中锁定）。

**POST `/debug/reset/`** — 重置运行结果（req1）

```json
// 请求（不传 node_ids 则全量重置）
{"template_id": 123, "node_ids": ["node_a", "node_b"]}
// 响应 data
{"reset_node_ids": ["node_a", "node_b"]}
```

**POST `/debug/reset_impact/`** — 变更影响（只读，req4）

```json
// 请求（后端读取 draft 快照与 tree_fingerprint diff）
{"template_id": 123}
// 响应 data
{
  "reset_node_ids": ["node_b", "node_c"],
  "reasons": {
    "node_b": "上游节点 node_a 配置变更",
    "node_c": "消费了 node_b 的输出变量"
  }
}
```

**POST `/debug/terminate/`** — 终止（req8）

```json
// 请求（传 node_id 则节点级强制失败，否则整体 revoke）
{"template_id": 123, "node_id": "node_xxx"}
// 单节点终止响应 data：节点已恢复为未调试
{"status": "idle", "reset_node_ids": ["node_xxx"]}

// 全局终止请求（不传 node_id）
{"template_id": 123}
// 全局终止响应 data：继续轮询 context，直到 status=idle、last_run_status=revoked
{"status": "terminating"}
```

**GET `/debug/history/`** — 调试历史（req13）

```json
// 响应 data
{
  "runs": [
    {"task_id": 456, "operator": "dannydeng", "started_at": "2026-06-25T14:00:00", "status": "finished", "inputs_summary": {"${biz_id}": "100"}}
  ]
}
```

**GET `/debug/input_schema/`** — 输入常量元数据（req14）

```json
// 响应 data
{
  "fields": [
    {"key": "${biz_id}", "name": "业务", "type": "string", "default": "", "required": true}
  ]
}
```

### 复用的任务详情接口（不重复造）

节点级重数据复用现有"任务详情"套件，凭 DEBUG `task_id` 或 `log_ref.instance_id` 调用：

| 用途 | 复用接口 | 入参 |
|---|---|---|
| 节点状态树 + 耗时 | `get_task_states`（任务状态） | DEBUG `task_id` |
| 单实例全局变量 | `render_current_constants` | DEBUG `task_id`（注意：仅反映该实例引擎 context，与统一 `global_vars` 可能发散） |
| 节点详情 / 输入输出 | `get_node_detail` / `get_node_data` | `log_ref.instance_id` + `node_id` |
| 节点日志 | `get_node_log` | `log_ref.instance_id` + `node_id` + `version` |

> mock 节点不经引擎，无上述引擎数据，其状态/输出/错误一律由 `DebugNodeState` 提供。

## 需求覆盖核对

- req1 全局调试：`global_run` + 从零重置（保留 mock）+ DEBUG 任务整体运行。✓
- req2 单步调试：`step_run` + 基于全局变量可用性的可执行性判定。✓
- req3 统一上下文：全局/单步共写同一 `DebugContext`/`DebugNodeState`；`context` 接口作为聚合层统一读取，节点级重数据复用任务详情接口。✓
- req4 变更重置：依赖图并集闭包 + 后端 diff 的 `reset_impact` 只读告知。✓
- req5 mock 单步：`step_run(mode=mock)` / `node_mock` 直接设输出并按 `source_act/source_key` 回写全局变量；方案 A 下 `node_mock` 设输出即置 `execution_mode=mock`。✓
- req6 旧 mock 兼容：统一 per-node 模型 + 运行时物化 `TaskMockData` + `TemplateMockData` 作预设来源。✓
- req7 禁止运行中改配置：`status=running` 锁编辑/重置。✓
- req8 即时终止：`terminate` 复用 `revoke_pipeline` / `forced_fail_activity`。✓
- req9 手动输入试运行：`step_run` 支持 `input_overrides`，绕过依赖检查直接以传入值运行。✓
- req10 编辑上下文变量：`context_var` 直接 set `global_vars`，不重跑上游。✓
- req11 mock 失败注入：`mock_result=fail` + `mock_error`，单步直接置失败、全局调试经扩展后的 `mock_execute` 触发引擎失败流程。✓
- req12 调试态可观测：`DebugNodeState` 记录 `duration_ms`/`error_detail`/`log_ref`（引擎引用）+ 网关分支求值结果；详情/日志复用现有任务详情接口。✓
- req13 调试历史：`history` 接口基于保留的 DEBUG 任务实例列出历次运行。✓
- req14 输入复用/元数据：`last_inputs` 预填 + `input_schema` 暴露必填常量。✓

## 未来扩展（非本期）

- 子流程节点 mock（需扩展引擎短路或在子流程边界注入）。
- 从指定节点续跑 / 部分重跑（引擎部分运行，复用上下文上游）。
- 网关分支强制走向（强制指定分支）。
- 断点 / 条件断点（当前单步调试 req2 已基本覆盖手动断点场景）。
- 批量调试 / 测试集（多组输入运行与结果对比）。
- 性能分析（火焰图 / 耗时排序）、失败级联可视化等前端可观测能力。
- 生产任务回放、自动化回归、智能诊断。
