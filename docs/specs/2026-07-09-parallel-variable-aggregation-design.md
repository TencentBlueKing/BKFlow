# BKFlow 并行网关变量聚合方案

> 状态：设计中（交互流转已按方案 1 定稿：向导留在节点配置语境）
> 关联 ADR：`docs/specs/2026-06-29-aggregate-variable-vs-node-adr.md`
> 关联原型：`prototypes/output/parallel-variable-aggregation/`
> 关联 TAPD：https://tapd.woa.com/tapd_fe/70120217/story/detail/1070120217135616034

## 1. 背景与问题

BKFlow（底层 bamboo-engine）的上下文是**扁平 key-value 池**：

- `Context.hydrate()` 把所有变量铺平成一个 dict
- `SpliceVariable` 通过 `${ref}` 模板引用其他变量
- 节点输出经 `Context.extract_outputs()` 写回 pool

**核心问题**：并行网关（ParallelGateway）下，多个分支若使用**同一个 key**（如 `${result}`）作为输出变量，写回时走 `extract_outputs` 的非循环分支逻辑：

```python
update[target_key] = ContextValue(key=target_key, type=PLAIN, value=...)
self.runtime.upsert_plain_context_values(...)  # 后写覆盖前写，无追加语义
```

→ 执行到下游时，全局 pool 里只剩**最后一个写入的值**，其余分支结果被覆盖丢失。

**已有线索**：`extract_outputs` 中 `loop_enabled` 节点已实现"同一 key 多次写入 → append 成 list"（`loop_outputs_list.append`）。聚合能力可在此基础上泛化。

## 2. 方案选型

最终选择 **方案 B：聚合变量类型**（而非独立聚合节点）。详见 ADR。

| 维度 | 聚合节点 | 聚合变量类型（选中） |
|---|---|---|
| 用户额外操作 | 拖节点 + 配置 | 设第二个同名输出时弹窗确认（更轻） |
| 拓扑约束 | 必须在汇聚网关之后 | 无 |
| 认知成本 | 多一个"聚合节点"概念 | 多一个"变量升级为聚合类型"概念 |
| 下游影响 | 引用新变量，旧变量不变 | 旧变量类型升级，需提示下游确认 |
| 引擎改动 | 新插件 + glob 收集 | 泛化 loop 累积机制 + 并发 append |
| 优雅度 | 中 | 高 |

## 3. 用户交互流程（核心）

> 交互细节见第 6 节；简易设计稿见 `prototypes/output/parallel-variable-aggregation/designs/`。

### 3.0 现状约束（重要 — 决定了交互形态）

前端现有 `ReuseVarDialog.vue`（`frontend/src/views/template/TemplateEdit/NodeConfig/ReuseVarDialog.vue`）在节点输出 key 与全局变量同名时弹出，现有「创建方式」如下：

| 情况 | 可选创建方式 | 默认 |
|---|---|---|
| key 已存在 + 有可复用变量 | 变量复用 / 手动创建 | 变量复用 |
| key 已存在 + 无可复用变量 | 仅手动创建（顶部告警「已存在相同KEY的变量，请新建变量」） | 手动创建 |
| key 不存在 + 有可复用变量 | 自动创建 / 变量复用 / 手动创建 | 自动创建 |
| key 不存在 | 仅手动创建 | 手动创建 |

**关键：现状不存在「覆盖」这个独立语义。** 两个节点输出到同一 key，走的是「变量复用」——它们引用**同一个全局变量对象**，运行期自然就是后写覆盖前写（bamboo `extract_outputs` 默认行为）。另有一条硬校验（key validator 最后一条）：`if (value in constants) return false`，提示「变量KEY值已存在」，阻止手动填同名 key 提交。

### 3.1 修正后的三选一

所以本需求**真正新增的只有「聚合」路径 + 校验放行**，另两项是复用现有 `ReuseVarDialog` 能力：

| 选项 | 是否新增 | 对应现状 | 说明 |
|---|---|---|---|
| **聚合到 result** | ✅ 新增 | 无 | key 升级为聚合变量，引擎累积（本需求核心） |
| **复用 result**（原“覆盖”） | 复用现有 | 变量复用 | 两节点引用同一全局变量，后写覆盖前写——**即现状默认行为**，不是新开关 |
| **改个名字** | 复用现有 | 手动创建 | 用户其实想要独立变量 |

### 3.2 交互步骤（方案 1：向导留在节点配置语境）

> **决策（2026-07-09）**：创建期升级路径**不跳转**到流程顶栏「全局变量」侧滑。  
> 原因：现网「节点配置」与「全局变量」侧滑互斥；若屏 1 Dialog「下一步」直接打开全局变量编辑，会出现不合理的场景切换。  
> 「全局变量 > 编辑」仅作为**事后微调**入口（改聚合方式、看来源），不是创建向导的下一步。

1. **分支 1** 配置节点输出 `result` → 普通单值全局变量（不弹窗）
2. **分支 2** 也设 `result` → 在**节点配置仍打开**时弹出 `ReuseVarDialog`（可扩展为多步向导），`sameKeyExist` 时**新增「聚合」选项**：
   - 聚合到 result（升级为聚合变量）
   - 复用 result（沿用同名全局变量，后写覆盖前写 — 现有默认）
   - 手动创建（改名为独立变量）
3. 用户选「聚合」后，**仍在同一 Dialog / 节点配置语境内**进入下一步：配置**聚合方式**（列表默认 / 字典）+ 只读展示来源与运行期 namespace
4. 若存在下游 `${result}` 引用，**同链路内**进入引用影响确认（可同 Dialog 第三步，或紧随其后的确认层）；确认后关闭 Dialog，**仍留在节点配置**，用户点「确定」落盘节点配置
5. （可选）事后从流程顶栏打开「全局变量 > 编辑 result」微调聚合策略——与创建向导解耦

## 4. 关键设计点

### 4.1 并行作用域内唯一（校验规则改造）
- 现状：BKFlow 上层（bkflow-woa 前端 `ReuseVarDialog.vue`）做 key 唯一校验（**bamboo-engine validator 本身不校验输出 key 重名**，只管图连通性 + 网关匹配）
- **具体放行点**：`ReuseVarDialog.vue` 中 key 的 validator 最后一条 `if (value in $this.constants) return false`（提示「变量KEY值已存在」）——当用户选「聚合」时**跳过/放行该判定**
- 「创建方式」下拉在 `sameKeyExist` 时**新增一个“聚合”选项**；选中后 `onConfirm` emit 新 action（如 `'aggregate'`）携聚合方式配置
- 作用域判断：静态分析 pipeline_tree，同分支内 key 重复 ❌ 拦截；跨分支同名 ✅ 放行并标记为「并行聚合候选」

### 4.2 变量类型升级语义
- 单值变量 → 聚合变量是一次**类型状态变更**
- 升级时必须高亮所有 `${result}` 引用点，要求用户确认（这是本方案唯一比聚合节点多出的认知成本）

### 4.3 聚合方式归属
- 聚合方式挂在**聚合变量自身**（变量编辑面板），不挂在节点上
- 一个聚合变量 = 一份统一策略，避免"分支1要list、分支2要dict"的矛盾
- dict 模式下，key = 分支标识（由引擎运行期自动填充，见 4.4）

### 4.4 运行期 namespace 底座（对用户透明）
- 并行网关 `runtime.fork(...)` 展开分支时，每个分支有唯一 process_id
- 引擎在 `extract_outputs` 写回时，自动给聚合变量的写入加 namespace 后缀（如 `result@<process_id>` 或分支序号），**用户全程无感**
- 聚合消费：按逻辑 key glob 匹配 `result@*`，按分支序号收集成有序结果

### 4.5 并发写原子性（最硬的一块）
- 聚合本质是多个并发分支往同一 list append
- `读现有 list → append → 写回` 三步非原子，必须保证原子性：
  - 行锁（`select_for_update`）或
  - DB 层原子 append / 乐观锁重试
- 需确认 `loop_enabled` 现有路径是否真并发安全（循环通常串行，并行才是新挑战）

## 5. 实现改动点清单

| 层 | 改动 | 文件/模块 |
|---|---|---|
| 引擎 | `extract_outputs` 泛化 list 累积；fork 注入 namespace | `bamboo_engine/context.py`、`bamboo_engine/handlers/parallel_gateway.py` |
| 引擎 | 并发 append 原子性保障 | runtime `upsert_plain_context_values` 实现层 |
| BKFlow | 校验规则：`ReuseVarDialog` key validator 的 `value in constants` 在聚合场景放行；新增「聚合」创建方式 + emit `aggregate` action | `frontend/src/views/template/TemplateEdit/NodeConfig/ReuseVarDialog.vue` |
| BKFlow | 第二同名输出弹窗、聚合方式编辑、类型升级提示 | bkflow-woa 前端 + 变量模型 |
| BKFlow | 编排期静态回溯并行作用域 | bkflow-woa 编排器 |

## 6. 设计稿与交互细节（方案 1 定稿）

### 6.1 设计稿清单

原型与简易设计稿目录：`prototypes/output/parallel-variable-aggregation/`（含 `screens/` / `shots/` / `designs/`）。

- [x] 屏 1：分支同名输出「三选一」— 节点配置 + Dialog（向导第 1 步）
- [x] 屏 2：聚合方式 / 来源 — **同 Dialog 向导第 2 步**（不打开全局变量侧滑）
- [x] 屏 3：下游引用确认 — **同链路第 3 步**（仍在节点配置语境）
- [x] 屏 4：分支联动与异常态
- [x] 屏 5：运行结果预览

### 6.2 交互细节（方案 1）

**A. 创建向导（节点配置语境，ReuseVarDialog 扩展为多步）**
- 触发：`sameKeyExist` 且跨并行分支同名；第 1 个分支配置不弹窗
- **步骤 1 · 创建方式**：聚合到 result（推荐）/ 复用 result / 手动创建；选聚合时放行 `value in constants`
- **不聚合时（复用 / 手动）**：步骤 2 / 3 置灰不可点；「下一步：设置聚合方式」禁用；底栏仅为「取消 / 确定」（对齐现网单步 Dialog），确定后关闭，不进入聚合配置
- **步骤 2 · 聚合方式**（仅选聚合后可进）：默认列表；可选字典；只读展示来源表 + 运行期 namespace
- **步骤 3 · 引用确认**（有下游引用时）：高亮 `${result}` 引用点，确认后才完成升级
- 完成后关闭 Dialog，**仍留在节点配置**；用户点节点配置「确定」落盘
- **禁止**：步骤间跳转到「全局变量」侧滑（与节点配置互斥）

**B. 事后编辑（可选，非创建必经）**
- 流程顶栏 →「全局变量 > 编辑 result」：微调聚合方式 / 看来源
- 与创建向导解耦，不作为屏 1「下一步」目标

**C. dict 模式分支标识展示**
- key 取分支稳定序号（如 `branch_1`/`branch_2`）；运行期 namespace 自动填充，用户只读

**D. 增删分支联动**
- 新增分支写同名 key：自动并入
- 删除来源：提示来源减少；仅剩 1 个来源时建议降级但不强制

### 6.3 仍需确认（技术 / 决策）
- [ ] 并发 append 的具体实现（行锁 `select_for_update` vs DB 原子 append / 乐观锁重试）
- [ ] `loop_enabled` 现有累积路径在并行场景下是否真并发安全
- [ ] 子流程场景下聚合变量的冒泡规则
- [ ] 「温馨提示」是否做成非阻断浅色提示引导用户加聚合（vs 仅弹窗）

## 7. 关联

- TAPD 需求：https://tapd.woa.com/tapd_fe/70120217/story/detail/1070120217135616034 （短 ID：`135616034`）
- 原型：`prototypes/output/parallel-variable-aggregation/README.md`
- 源码：`frontend/src/views/template/TemplateEdit/NodeConfig/ReuseVarDialog.vue`、`TabGlobalVariables/`、bamboo-engine context/parallel_gateway
