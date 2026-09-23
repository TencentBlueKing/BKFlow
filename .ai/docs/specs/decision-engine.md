---
name: bkflow-decision-engine
description: Use when working with BKFlow's decision table feature, implementing DMN integration, designing the relationship between decision tables and workflow templates, or understanding how the decision plugin executes rules.
---

# BKFlow 决策引擎

## Overview

BKFlow 集成了基于 DMN（Decision Model Notation）标准的决策引擎，通过 bkflow-dmn SDK 实现，支持两种集成方式：流程内决策表（强绑定）和独立决策表资源（可复用）。当前优先实现独立决策表资源方式。

## 两种集成方式对比

### 方式一：独立决策表资源（当前主方案）

- 决策表作为独立资源存在于流程外，可跨流程复用
- 决策表节点通过 ID 引用对应决策表
- 权限管理通过 Token 授权
- 接入系统可通过 API 配置决策表与流程模板的映射关系
- **适用场景**：同一套业务规则需要被多个流程引用时

### 方式二：流程内决策表（已实现，较简单）

- 决策表数据与流程强绑定，权限完全依赖流程权限
- 实现简单，但决策表不能跨流程复用
- 规则配置可以直接使用流程的全局变量

## 独立决策表资源数据模型

决策表字段：

- `id`, `name`, `desc`
- `space_id`（空间隔离）
- `scope_type`, `scope_value`（业务范围）
- `data`（JSON，决策表内容）
- `is_deleted`, `create_time`, `update_time`, `creator`, `updator`
- `extra_info`（扩展字段）

## 决策表与流程映射关系

接入系统可通过 API 配置决策表与流程模板的映射：

- 映射关系为可选配置（可为空）
- 未配置映射时，决策表插件默认获取当前空间和 scope 下的所有决策表
- 配置映射后，只展示映射表中关联的决策表

## 执行约束

> **安全约束**：决策表插件执行时，通过决策表 ID 获取资源，必须校验决策表 ID 属于当前空间，防止通过 `create_task_with_pipeline_tree` 传入其他空间的决策表 ID 造成跨空间数据访问。

执行链路：

```
task module → interface module (获取决策表资源) → bkflow-dmn (执行规则) → 输出决策结果
```

engine 模块执行插件时，需通过 interface internal client 从 interface 模块获取决策表资源，再交给 bkflow-dmn 消费。

## bkflow-dmn SDK

- 基于 Python 的 DMN 库
- 使用 FEEL（Friendly Enough Expression Language）作为描述语言
- FEEL 解析器为独立 SDK：`bkflow-feel`
- DMN 执行：根据输入字段匹配规则，输出决策结果

## 接入系统使用决策表的流程

1. 接入系统创建决策表（或由用户在 BKFlow 管理端创建）
2. 可选：接入系统通过 API 配置决策表与流程模板的映射
3. 用户在流程画布中添加决策表插件节点
4. 决策表插件节点拉取当前 scope 下（或映射关系中）的决策表列表
5. 用户选择决策表并配置输入/输出字段映射
6. 任务执行时，engine 调用决策表插件执行 DMN 规则

## 权限管理

- **编辑决策表**：Token 授权
- **查看决策表**：Token 授权
- **管理端**：空间管理员可操作所有决策表资源
