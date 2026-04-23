---
name: bkflow-design-patterns
description: Use when working on advanced BKFlow features like pipeline_tree protocol changes, trigger systems, credential management, canvas token security, or researching dynamic workflow (CMMN) implementation.
---

# BKFlow 设计模式与方案

## Overview

本文汇总 BKFlow 的关键设计模式，包括 PipelineTree 协议分层、触发器机制、凭证管理安全设计、画布 Token 鉴权方案，以及动态流程编排（CMMN）的调研结论。

## 可信语义设计范式

### 背景

BKFlow 在承接外部系统接入、插件调用或上下文兼容场景时，可能需要向下游传递某些会被直接信任的语义，例如“归属对象”“执行身份”“作用域”。  
这类信息一旦被下游直接信任，就不再只是普通字段，而会变成 BKFlow 对外输出的系统事实。

因此，BKFlow 在设计此类能力时，需要遵循一组更通用的可信语义范式，而不能只把它看成“多传几个字段”。

### 已确认的设计原则

#### 1. 被下游直接信任的语义，必须由 BKFlow 负责认定

凡是会被外部系统或插件直接信任的语义，BKFlow 不能只做透传，而要对其可信性负责。  
这类语义不是普通字段，而是 BKFlow 对外承诺的系统事实。

**正向例子：**

- 某个“业务归属”由 BKFlow 根据空间绑定、任务上下文和权限校验后生成，再传给插件。

**反向例子：**

- 用户在请求里填一个 `biz=42`，BKFlow 原样塞进插件上下文；插件又默认信任这个值，最终形成“冒用某业务名义调用能力”的风险。

#### 2. 高风险语义不能只是普通参数，要和普通输入分层

高风险语义不能与普通业务输入处于同一层级。  
普通参数可以由用户自由填写；高风险语义必须来自系统绑定、权限校验或受控配置，而不能被视为“和普通参数一样的输入”。

**正向例子：**

- 用户可以填写“目标主机”“部署批次”“备注”等普通参数。
- “任务代表哪个业务执行”“以谁的身份对外调用”这类语义，必须走系统侧的专门机制。

**反向例子：**

- 把 `bk_biz_id`、`executor`、`scope_value` 这类字段和普通 `custom_context` 混放，允许用户直接覆盖。

#### 3. 不确定时默认保守，但失败必须可解释

当 BKFlow 无法确认某个高风险语义是否可信时，应优先拒绝或降级，而不是乐观放行。  
但系统不能只拦住，还要把原因说清楚，让调用方知道是缺权限、缺绑定，还是缺可信来源。

**正向例子：**

- 系统发现任务缺少可信的业务归属时，明确拒绝进入某类高风险调用，并提示“当前空间未配置可信业务绑定”。

**反向例子：**

- 系统在无法确认语义可信性时，擅自兜底成某个默认值继续执行，事后又无法解释为什么这么做。

### 已确认的典型 Bad Case

#### 1. 空间管理员自助开启高信任能力，并冒用业务身份调用危险插件

**场景：**

- 某个用户自己创建空间。
- 空间侧可以自助打开某种“高级上下文兼容”或“高信任语义”能力。
- 该用户填入一个并不真正属于自己的业务 ID。
- 下游插件默认信任 BKFlow 传过去的业务语义，并据此执行高风险操作。

**结论：**

这是典型的“把应由平台控制的信任边界，下放成业务侧自助能力”的漏洞。

#### 2. 未被平台整体信任的空间，如果固定绑定业务时不校验权限，会被乱配

**场景：**

- 某个空间本身没有被系统管理员认可为高信任空间。
- 但空间管理员仍然希望在空间内使用这类高风险语义。
- 如果系统允许其直接把空间固定绑定到任意业务，而不验证他是否对该业务有权限，就会形成越权配置。

**结论：**

即便是“受限模式”，也不能跳过绑定时的权限验证；否则只是把动态冒用，换成了静态冒用。

### 已确认的硬约束

- 只有系统管理员才能给某些空间开高信任能力。
- 未被平台认可的空间，也可以在受限前提下使用这类语义。

### 待定项（记录保留，但不作为设计原则）

以下内容来自历史 brainstorming 讨论，保留在此供后续设计时参考。  
它们当前**不是** BKFlow 设计原则，也**不应**在具体方案中被视为既定约束：

- 兼容历史输入可以，但内核语义必须统一。
- 同一个语义必须在整条链路上保持一致。
- 能力开放要按信任等级分层，而不是一个总开关。
- 只要出现替别人或替别的范围执行，就要显式建模成委托。
- 高风险能力不要挂在普通配置体系下面。
- 灵活性不是默认目标，可治理性才是。
- 审计不是补充信息，而是产品主语义的一部分。
- 允许用户通过普通任务参数直接覆盖系统级身份或作用域语义。
- 入口兼容字段长期不收敛，导致系统内部同时存在多套含义相同但名字不同的模型。
- 页面展示、运行时上下文、请求头和审计日志对同一语义的解释不一致。
- 以“默认值”伪装“委托关系”，导致实际是在共享某个人的业务权限执行，但系统内没有清晰的责任边界。

## PipelineTree 协议分层设计

### 核心拆分原则

将 pipeline_tree 拆分为两个独立协议：

- **engine_pipeline_tree**：引擎执行所需的最小数据，是流程/任务的最简协议
- **canvas_pipeline_tree**：画布展示和前端渲染所需的数据，与引擎执行无关

> **约束**：两层数据严格分离，不允许 canvas 数据污染 engine 协议。

### engine_pipeline_tree 核心结构

```
Pipeline:
  id, name
  nodes: List[Node]
  outputs: List[Constant]

ComponentNode:
  component: Component  # code, version, data: List[ComponentField]
  skippable, retryable, error_ignorable
  auto_retry: AutoRetryConfig   # enable, interval, times
  timeout_config: TimeoutConfig  # enable, seconds, action

ExclusiveGateway:
  conditions: List[Condition]  # id, name, lang(boolrule/FEEL), expr
  converge_gateway_id: str

ParallelGateway:
  converge_gateway_id: str

Constant:
  key, name, type, value
  source_type
  pre_render_mako: bool = False
```

### canvas_pipeline_tree 核心结构

```
CPT {
  nodes: [{ id, type, position: {x,y}, config }]
  edges: [{ id, source: {id, arrow}, target: {id, arrow}, config }]
  constants?: { [key]: ConstantConfig }
}
```

## 触发器（Trigger）设计

### 远程触发器机制

- 创建时指定 `secret_key` 作为调用凭证，调用时携带在路径上
- 支持条件过滤：创建时指定条件表达式，调用时传入数据，满足条件才触发
- 条件格式：`test.fields="test"` 对应调用时传入 `{"test": {"fields": "test"}}`

### 定时触发器数据一致性问题

> **核心设计决策**：定时触发器存储 pipeline_tree 有两种方案：
> - **不存储**：每次从 interface 获取最新模板，无一致性问题，但高频触发会增大 interface 压力
> - **直接存储**：避免反向读取，但存在模板更新后的数据一致性问题（需双写事务或接受延迟一致）

### 触发器表关键字段

```python
template_id, is_enabled, name
condition: JSONField      # 触发条件
config: JSONField         # 触发配置
secret_key                # 远程触发凭证
type: interval/remote
```

## 凭证管理（Credential）

### 设计原则

- **加密存储**：密钥字段使用加密算法存储（推荐使用国密），接口永远不返回密钥原文
- **抽象化存储**：所有凭证类型统一用 JSON 存储，不同类型凭证有对应的 Handler 类处理
- **空间级别隔离**：凭证与空间绑定，`space_id` 是核心隔离维度

### 凭证数据模型

```json
{
  "id": "凭证ID",
  "space_id": "空间ID",
  "name": "凭证名",
  "desc": "描述",
  "type": "凭证类型",
  "data": "加密后的凭证值（JSON）",
  "create_time": "...",
  "update_time": "..."
}
```

### Handler 模式

每种凭证类型对应一个 Handler 类，统一接口：

```python
class XxxCredentialHandler:
    type = "Xxx"

    class CredentialSchema(serializer.Serializer):
        pass

    def detail(self):
        # 返回脱敏后的展示数据
        pass

    def save(self):
        # 加密存储到 data 字段
        pass

    def content(self):
        # 返回解密后的完整凭证内容（供内部模块消费）
        pass
```

> **约束**：`content()` 方法仅供内部模块使用，不能通过 API 暴露给外部。

### 当前支持的凭证类型

- **密码**：用于流程编排中的身份验证
- **APPID+SecretKey**：用于 API 插件请求的系统身份

## 画布 Token 鉴权

### Token 数据模型

| 字段 | 说明 |
|------|------|
| `token` | UUID 生成，主键 |
| `create_time` | 创建时间 |
| `expired_time` | 过期时间（建索引） |
| `space_id` | 空间 ID |
| `resource_id` | 资源 ID |
| `resource_type` | 流程/任务 |
| `user` | 用户名 |
| `extra_info` | 扩展信息（权限类型等） |

### Token 机制约束

- Token 与用户绑定，由接入系统代替用户向 BKFlow 申请
- Token 生效范围为第一层级资源（流程/任务），持有该资源 Token 可访问该资源的所有子 API
- Token 必须设置有效期，过期后鉴权失败，需定时任务清理过期 Token
- 同一用户多次访问同一资源时，返回系统中未过期的已有 Token，不重复创建
- 支持自动续期（`token_auto_renewal`）：用户操作过程中自动延长一个周期

### 申请 Token 所需参数

```json
{
  "space_id": "",
  "user": "",
  "resource_type": "",
  "resource_id": "",
  "permission_type": "view/edit"
}
```

## 动态流程编排（CMMN）调研结论

### 背景

BKFlow 当前实现了 BPMN（结构化流程）和 DMN（决策）。业务方需要动态流程编排能力，对应 CMMN（Case Management Model and Notation）标准。

### CMMN 核心概念

关键机制：**哨兵（Sentry）** = onParts（监控其他计划项状态）+ ifPart（表达式条件），两者都满足时触发。

### 初步设计的 CMMN 流程描述协议

```json
{
  "case_id": "UUID",
  "case_name": "xxx",
  "plan_items": [
    {
      "id": "UUID",
      "name": "xxx",
      "component": {"code": "...", "data": {}, "version": "..."},
      "is_stage": false,
      "child_plan_items": [],
      "entry_criterion": ["sentry_id"],
      "exit_criterion": ["sentry_id"]
    }
  ],
  "sentrys": [
    {
      "id": "UUID",
      "planitem_id": "绑定的计划项ID",
      "conditions": [
        {
          "plan_item_id": "监控的计划项ID",
          "target_plan_item_status": 2
        }
      ],
      "expression": "FEEL表达式",
      "sentry_type": 0
    }
  ]
}
```

### 核心 SDK 类设计

- **CmmnConvertor**：解析 CMMN 描述协议，写入数据库
- **CmmnContextManager**：上下文管理器
- **CmmnComponentExecutor**：执行计划项绑定的插件
- **SentryManager**：判定计划项哨兵状态

> **当前状态**：CMMN 功能尚在调研阶段，未正式实现，参考 Flowable 开源项目的实现方案。
