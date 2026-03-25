# 部署架构

## 概述

BKFlow 采用 **Interface + Engine 双模块分离架构**进行部署。在同一个蓝鲸 PaaS 应用下，Interface 和 Engine 作为独立的模块分别部署，各自拥有独立的进程、数据库和消息队列。

核心特点：

- **一个 Interface 对应多个 Engine**：Interface 模块是统一的资源管理和 API 入口，Engine 模块负责任务执行，可按需部署多个实例
- **空间与 Engine 绑定**：每个空间（Space）绑定到一个特定的 Engine 模块，Interface 根据空间 ID 将请求路由到对应的 Engine
- **资源隔离**：不同 Engine 模块之间的计算资源和数据存储相互隔离

## 架构示意

```
                    ┌──────────────────────────────┐
                    │           APIGW              │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     Interface 模块 (default)  │
                    │  ┌────────────────────────┐   │
                    │  │ 空间/模板/插件/权限管理 │   │
                    │  │ APIGW 网关接口         │   │
                    │  │ 前端静态资源           │   │
                    │  └────────────────────────┘   │
                    │        ModuleInfo 路由表      │
                    │   ┌─────────┬─────────────┐   │
                    │   │ space=0 │ space=1 ... │   │
                    │   │→engine-A│→engine-B ...│   │
                    │   └─────────┴─────────────┘   │
                    └───┬─────────────┬─────────────┘
           内部 API     │             │      内部 API
                ┌───────▼──────┐ ┌────▼──────────┐
                │ Engine 模块 A │ │ Engine 模块 B  │  ...可继续扩展
                │ (code=default)│ │ (code=xxx)    │
                │              │ │               │
                │ - 任务执行    │ │ - 任务执行     │
                │ - Pipeline   │ │ - Pipeline    │
                │ - Celery     │ │ - Celery      │
                │   Workers    │ │   Workers     │
                └──────────────┘ └───────────────┘
```

## 模块职责

### Interface 模块

Interface 是 BKFlow 的**统一入口和资源管理层**，全局仅部署一个实例。

| 职责 | 说明 |
|---|---|
| API 网关 | 对外暴露 BKFlow Gateway API，经由蓝鲸 APIGW 注册和鉴权 |
| 资源管理 | 空间、流程模板、插件、凭证、决策表等上层资源的 CRUD |
| 前端服务 | 数据管理端和画布编排页面的静态资源托管 |
| Engine 路由 | 根据空间 ID 查询 `ModuleInfo` 表，将任务执行请求转发到对应 Engine |
| 权限管理 | 用户认证、API 鉴权和权限校验 |

### Engine 模块

Engine 是 BKFlow 的**任务执行层**，可部署多个实例，每个实例通过唯一的 `BKFLOW_MODULE_CODE` 标识。

| 职责 | 说明 |
|---|---|
| 任务执行 | 基于 bamboo-engine 驱动 Pipeline 流程的实际执行 |
| 插件调度 | 执行节点对应的插件逻辑（内置插件、API 插件、蓝鲸插件） |
| Celery Worker | 提供调度队列、执行队列、通用任务队列等多组 Worker |
| 节点超时管理 | 独立进程监控节点执行超时 |
| 过期任务清理 | 定时清理过期的任务数据 |

## 模块间通信

Interface 和 Engine 之间通过**内部 HTTP API + Token 鉴权**通信，双向调用：

| 方向 | 场景 | 鉴权方式 |
|---|---|---|
| Interface → Engine | 创建/操作任务、查询任务状态 | `APP_INTERNAL_TOKEN`（Engine 侧校验） |
| Engine → Interface | 回调通知、获取决策表/空间配置等资源数据 | `INTERFACE_APP_INTERNAL_TOKEN`（Interface 侧校验） |

**关键约束**：Engine 模块不能直接访问 Interface 的数据库，必须通过 Interface 内部 API 获取资源数据。

## Engine 路由机制

Interface 通过 `ModuleInfo` 模型管理所有 Engine 模块的注册信息：

| 字段 | 说明 |
|---|---|
| `space_id` | 空间 ID（唯一键），每个空间绑定一个 Engine |
| `code` | Engine 模块标识，对应 `BKFLOW_MODULE_CODE` |
| `url` | Engine 模块的服务地址 |
| `token` | Interface 调用该 Engine 的鉴权 Token |
| `isolation_level` | 资源隔离级别 |

`space_id=0` 为默认 Engine 模块，未显式绑定 Engine 的空间将路由到默认模块。

## 资源隔离

每个 Engine 模块支持两种资源隔离级别，通过 `BKFLOW_RESOURCE_ISOLATION_LEVEL` 配置：

| 隔离级别 | 说明 |
|---|---|
| `only_calculation` | **仅计算隔离**：共享数据库，仅隔离 Celery Broker 和 Worker 队列 |
| `all_resource` | **全资源隔离**：独立数据库 + 独立 Celery Broker + 独立 Worker 队列 |

无论哪种隔离级别，每个 Engine 的 Celery 队列名称都包含 `BKFLOW_MODULE_CODE` 前缀，确保队列层面的隔离。

## 进程模型

### Interface 模块进程

| 进程 | 命令 | 说明 |
|---|---|---|
| `web` | `bin/start_web.sh`（gunicorn） | HTTP 服务 |
| `worker` | `celery worker -n interface_worker` | 异步任务处理（如蓝鲸插件同步） |
| `beat` | `celery beat` | 定时任务调度 |

### Engine 模块进程

| 进程 | 命令 | 说明 |
|---|---|---|
| `web` | `bin/start_web.sh`（gunicorn） | 接收 Interface 的内部 API 请求 |
| `er-e` | `celery worker -Q er_execute_${CODE}` | Pipeline 节点执行 Worker |
| `er-s` | `celery worker -Q er_schedule_${CODE}` | Pipeline 调度 Worker |
| `cworker` | `celery worker -Q celery,...,task_common_${CODE},...` | 通用任务 Worker |
| `timeout` | `python manage.py node_timeout_process` | 节点超时监控进程 |
| `beat` | `celery beat` | 定时任务调度（如过期任务清理） |
| `clean-worker` | `celery worker -Q clean_task_${CODE}` | 过期任务清理 Worker |

> `${CODE}` 为该 Engine 模块的 `BKFLOW_MODULE_CODE`。

## 公共组件依赖

| 组件 | 用途 | 备注 |
|---|---|---|
| MySQL | 数据持久化 | Interface 和各 Engine 模块各自拥有独立数据库 |
| RabbitMQ | Celery 消息队列 | 驱动任务调度和异步处理 |
| Redis | 分布式缓存 | Engine 模块使用，用于执行节点池等场景 |

## 关键环境变量

### 公共变量

| 变量 | 说明 |
|---|---|
| `BKFLOW_MODULE_TYPE` | 模块类型：`interface` 或 `engine` |
| `APP_INTERNAL_TOKEN` | 模块内部 API 鉴权 Token |

### Interface 专有

| 变量 | 说明 |
|---|---|
| `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY` | 默认 Engine 模块的服务地址 |
| `DEFAULT_ENGINE_APP_INTERNAL_TOKEN` | 调用默认 Engine 的鉴权 Token |
| `BK_APIGW_NAME` | 蓝鲸 APIGW 网关名称 |

### Engine 专有

| 变量 | 说明 |
|---|---|
| `BKFLOW_MODULE_CODE` | Engine 模块唯一标识（影响 Celery 队列名） |
| `BKFLOW_RESOURCE_ISOLATION_LEVEL` | 资源隔离级别 |
| `INTERFACE_APP_URL` | Interface 模块的服务地址 |
| `INTERFACE_APP_INTERNAL_TOKEN` | 调用 Interface 的鉴权 Token |
| `BKFLOW_CELERY_BROKER_URL` | Celery Broker 地址（隔离时独立配置） |
| `BKFLOW_DATABASE_*` | 独立数据库配置（`all_resource` 隔离级别时生效） |

## 扩展 Engine 模块

新增 Engine 模块的步骤：

1. 在蓝鲸 PaaS 平台中为应用创建新的模块，设置 `BKFLOW_MODULE_TYPE=engine` 及对应的 `BKFLOW_MODULE_CODE`
2. 根据隔离需求配置独立的数据库和 Celery Broker
3. 部署 Engine 模块的全部进程（er-e、er-s、cworker、timeout、web、beat、clean-worker）
4. 在 Interface 的管理端（Django Admin 或 ModuleInfo API）注册新 Engine 模块的信息（url、token、隔离级别）
5. 创建空间时指定绑定到新的 Engine 模块
