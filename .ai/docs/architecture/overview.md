---
name: bkflow-architecture
description: Use when understanding BKFlow's system architecture, module boundaries, deployment structure, or code organization — especially when making changes that affect inter-module communication, adding new modules, or understanding routing logic between interface and engine layers.
---

# BKFlow 系统架构

## Overview

BKFlow 是基于 Python 实现的 SaaS 流程引擎平台，采用 interface + engine 双模块分离架构。interface 模块负责资源管理和入口，engine 模块负责任务执行，两者通过内部 API 通信，并以空间 ID 为路由键进行 engine 路由。

## 核心模块职责边界

### interface 模块

- **职责**：空间、流程模板、任务、凭证等上层资源的管理入口；对外暴露 BKFlow Gateway API
- **调用关系**：接收来自 Web 页面、APIGW、engine 模块的三类请求
- **潜在单点风险**：interface 是当前的单点模块，若资源不足可基于场景（Web/API/Engine 回调）进行拆分，拆分后各子模块共享同一个 interface DB

### engine 模块

- **职责**：任务的实际执行单元，与空间强绑定，基于空间 ID 进行路由
- **隔离级别**：通过 `BKFLOW_RESOURCE_ISOLATION_LEVEL` 环境变量配置，支持 `all_resource` 级别实现完整资源隔离
- **模块标识**：每个 engine 实例有唯一的 `BKFLOW_MODULE_CODE`，Celery 队列名称包含此 code（如 `task_common_${BKFLOW_MODULE_CODE}`）

## 代码目录结构

```
bkflow/
├── admin/            # 管理员接口和模型
├── apigw/            # API 网关接口（对外暴露的接口维护在此）
├── bk_plugin/        # 蓝鲸插件模块（含同步拉取插件的异步任务）
├── conf/             # 配置模块（default + ieod上云版 + open社区版 分环境配置）
├── decision_table/   # 决策表模块
├── interface/        # interface 模块（对 task 模块的统一请求封装和路由视图）
├── permission/       # 统一鉴权封装
├── pipeline_plugins/ # 内置插件（含反向拉取插件信息接口和内置变量）
├── pipeline_web/     # 流程处理（预检 pipeline_tree、画布连线等）
├── plugin/           # 插件管理
├── space/            # 空间配置（接口 + 模型）
├── task/             # engine 模块目录（实际操作 task）
├── template/         # 流程模板（接口 + 模型）
└── utils/            # 工具模块
```

关键文件：

- `module_settings.py`：interface/engine 模块的分模块配置
- `env.py`：环境变量定义
- `webhook_resources.yaml`：Webhook 事件配置

## SDK 依赖关系

BKFlow 将核心能力抽象为独立 SDK。

## 公共组件依赖

- **MySQL**：资源数据持久化存储（interface 和 engine 各有独立 DB）
- **RabbitMQ**：消息队列，驱动任务执行调度和异步处理
- **Redis**：分布式缓存
- **必要依赖的蓝鲸服务**：蓝鲸统一登录、蓝鲸 APIGW、蓝鲸 PaaS 平台

## 部署架构设计约束

- engine 模块不能直接访问 interface DB，必须通过 interface 内部 API 获取资源数据（如决策表、空间配置）
- 空间与 engine 模块强绑定，engine 选择必须在创建空间或空间配置时明确指定
- API 必须经过蓝鲸 APIGW 注册，`callback_url` 等回调配置必须使用来自 APIGW 的 URL，不可使用直连地址
- Celery worker 队列命名含 `module_code`，不同 engine 实例的队列相互隔离，修改 `module_code` 会导致已有队列消息丢失

## 容器化部署结构

采用多阶段 Dockerfile 构建：

1. **frontend-builder**：Node 18 构建前端（`npm run build`），产物放入 `static/bkflow`
2. **python-builder**：Python 3.12-slim 安装依赖并复制代码
3. **最终镜像**：合并前后端产物，启动脚本为 `container_start.sh`

启动时根据 `BKPAAS_APP_MODULE_NAME == "default"` 判断是否执行 SaaS 初始化任务（`sync_saas_apigw`、`sync_superuser`、`sync_default_module` 等）。
