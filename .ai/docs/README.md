# BKFlow AI 参考文档

AI coding 时的架构与设计参考文档。与 `.ai/skills/` 配合使用：skills 告诉 AI **怎么做**，docs 告诉 AI **是什么**。

## 文档索引

### architecture/ — 系统架构

| 文档 | 路径 | 何时参考 |
|------|------|----------|
| 系统架构总览 | [architecture/overview.md](architecture/overview.md) | 理解模块关系、部署结构、修改跨模块代码时 |
| 核心概念 | [architecture/core-concepts.md](architecture/core-concepts.md) | 理解空间/模板/任务/节点/变量/插件等领域模型时 |

### design/ — 功能设计

| 文档 | 路径 | 何时参考 |
|------|------|----------|
| 任务执行 | [design/task-execution.md](design/task-execution.md) | 实现任务创建、执行控制、pipeline_tree 协议相关代码时 |
| 插件系统 | [design/plugin-system.md](design/plugin-system.md) | 开发 API 插件、理解插件元数据协议、配置插件凭证时 |
| 决策引擎 | [design/decision-engine.md](design/decision-engine.md) | 实现决策表功能、DMN 集成、决策表与流程映射时 |
| 空间配置 | [design/space-config.md](design/space-config.md) | 新增空间配置字段、修改 SpaceConfig 模型、理解存储策略时 |
| 设计模式 | [design/design-patterns.md](design/design-patterns.md) | 修改 pipeline_tree 协议、触发器、凭证管理、Token 鉴权、CMMN 调研时 |

### guides/ — 开发指南

| 文档 | 路径 | 何时参考 |
|------|------|----------|
| 开发指南 | [guides/dev-guide.md](guides/dev-guide.md) | 搭建本地开发环境、理解环境变量、容器化部署时 |

## 使用方式

每个文档的 YAML frontmatter 包含 `name` 和 `description` 字段，`description` 描述了该文档的适用场景。AI agent 可根据当前任务上下文匹配合适的文档进行参考。
