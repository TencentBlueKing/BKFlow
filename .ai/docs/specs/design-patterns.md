---
name: bkflow-design-patterns
description: Use when working on advanced BKFlow features like pipeline_tree protocol changes, trigger systems, credential management, canvas token security, or researching dynamic workflow (CMMN) implementation.
---

# BKFlow 设计模式与方案

## Overview

本文汇总 BKFlow 的关键设计模式，包括 PipelineTree 协议分层、触发器机制、凭证管理安全设计、画布 Token 鉴权方案，以及动态流程编排（CMMN）的调研结论。

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
