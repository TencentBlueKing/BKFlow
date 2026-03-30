---
name: bkflow-task-execution
description: Use when implementing task creation, execution control, canvas integration, understanding the pipeline_tree protocol, or designing workflows that involve the access system interacting with BKFlow APIs.
---

# BKFlow 任务执行

## Overview

BKFlow 提供两种接入模式：嵌入 BKFlow 画布（通过 Token 机制授权）和接入系统自建画布（通过 pipeline_tree 协议交互）。任务执行通过 bamboo-engine 驱动，节点执行过程包括变量渲染、插件执行和规则决策三个环节。

## 两种接入模式

### 模式一：嵌入 BKFlow 画布

接入系统不自建画布，将 BKFlow 画布嵌入到自己的应用中。

**交互流程**：

1. 接入系统调用 `create_space` API 注册空间，获取 `space_id`
2. 用户在接入系统触发创建流程/任务操作
3. 接入系统调用 BKFlow API 创建资源，获取资源 ID
4. 接入系统代替用户调用 `fetch canvas token` 获取 Token
5. 接入系统将资源 ID + Token 返回给用户
6. 用户携带 Token 和资源 ID 直接访问 BKFlow 画布

**关键约束**：

- Token 由接入系统代替用户申请，申请时需指定用户名、资源类型、资源 ID、权限类型
- Token 的生效范围是第一层级资源（流程/任务），拥有该流程 Token 的用户，所有该流程相关 API 请求均被放行
- Token 必须设置有效期，过期后鉴权失败，需由接入系统重新申请

### 模式二：接入系统自建画布

接入系统自建画布和流程管理，只依赖 BKFlow 进行任务执行。

必须理解 pipeline_tree 协议，在创建任务时将 pipeline_tree 作为参数传递给 BKFlow。

**交互流程**：

1. 注册空间
2. 用户在接入系统画布中编辑流程（接入系统自行管理）
3. 用户触发创建任务，接入系统将 pipeline_tree 传给 BKFlow 的 `create_task` API
4. BKFlow 根据 pipeline_tree 执行任务

## API 快速接入顺序

```
1. create_space          → 创建空间，获取 space_id
2. renew_space_config    → 配置空间参数
3. create_template       → 创建流程模板
4. create_task           → 基于模板创建任务实例
5. operate_task          → 执行/控制任务（启动/暂停/终止等）
```

所有 API 通过蓝鲸 APIGW 注册发布，接入系统需申请调用权限。

## pipeline_tree 协议

pipeline_tree 是流程/任务的核心数据协议，分为两个层：

### engine_pipeline_tree（引擎执行层）

存储引擎执行所需的最小数据集：

- **Pipeline**：包含节点列表（`nodes`）和输出变量（`outputs`）
- **节点类型**：`ComponentNode`（任务节点）、`ParallelGateway`、`ConvergeGateway`、`ExclusiveGateway`
- **变量（Constant）**：`key`、`value`、`type`、`source_type`、`pre_render_mako`
- **组件字段（ComponentField）**：`value`、`type`、`key`、`need_render`

> **约束**：engine_pipeline_tree 是最简协议，不包含画布展示信息。

### canvas_pipeline_tree（画布展示层）

存储画布渲染所需数据，与引擎执行无关：

- `nodes`：含位置信息（`position.x/y`）和配置（`config`）
- `edges`：连接关系，含来源/目标节点 ID 和标签
- `constants`：全局变量展示配置

> **设计原则**：两层数据严格分离，canvas_pipeline_tree 的修改不应影响 engine_pipeline_tree 的执行逻辑。

## 任务执行过程

引擎执行任务时的三个核心环节：

1. **变量渲染**：将全局变量（Constants）的值替换到节点输入参数中（`need_render=True` 的字段）
2. **节点执行**：根据节点输入参数调用对应插件的业务逻辑，得到节点输出
3. **规则决策**：通过决策表匹配规则，得到决策输出

## 开发工作流

主仓库使用 GitFlow 工作流：

- **功能特性**：develop 分支测试后合入 master
- **热修复**：直接基于 master 开发合入
- 每个新版本打 tag
- **测试环境**：上云预发布（`stag-dot-bkflow-eng-svc.bkapps-sz.woa.com`）
- **CI/CD**：上云部署 & 前端打包通过 DevOps 流水线自动化

## Celery 队列配置

engine 模块的 Celery Worker 需要监听以下队列（`${BKFLOW_MODULE_CODE}` 替换为实际模块 code）：

- `task_common_${BKFLOW_MODULE_CODE}`：通用任务队列
- `node_auto_retry_${BKFLOW_MODULE_CODE}`：节点自动重试
- `timeout_node_execute_${BKFLOW_MODULE_CODE}`：超时节点执行
- `er_schedule_${BKFLOW_MODULE_CODE}`：调度队列（独立 worker）
- `er_execute_${BKFLOW_MODULE_CODE}`：执行队列（独立 worker）
