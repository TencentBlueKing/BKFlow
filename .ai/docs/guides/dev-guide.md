---
name: bkflow-dev-guide
description: Use when setting up BKFlow development environment, understanding environment variables, managing Python/Node version requirements, working with the interface/engine dual-module local setup, or deploying BKFlow in containerized environments.
---

# BKFlow 开发指南

## Overview

BKFlow 采用 interface + engine 双模块架构，本地开发需分别启动两个服务。后端基于 Python 3.12（容器化版本，本地开发支持 3.9+），前端基于 Node.js 18+。本文专注于开发约定和架构约束，不含具体安装步骤。

## 关键环境变量

### 模块类型区分

```bash
BKFLOW_MODULE_TYPE=interface   # 或 engine
BKFLOW_MODULE_CODE=xxx         # engine 实例的唯一标识（影响 Celery 队列名）
BKFLOW_RESOURCE_ISOLATION_LEVEL=all_resource  # engine 资源隔离级别
```

### interface 模块关键变量

```bash
BKFLOW_MODULE_TYPE=interface
DB_NAME=bkflow-interface
APP_INTERNAL_TOKEN=xxx                   # 内部 API 鉴权 token
BKAPP_DEFAULT_ENGINE_MODULE_ENTRY=xxx    # engine 服务地址
DEFAULT_ENGINE_APP_INTERNAL_TOKEN=xxx    # interface 调用 engine 的 token
BKFLOW_CELERY_BROKER_URL=amqp://...
```

### engine 模块关键变量

```bash
BKFLOW_MODULE_TYPE=engine
BKFLOW_MODULE_CODE=xxx
DB_NAME=bkflow-default-engine
BKFLOW_DATABASE_NAME=bkflow-default-engine
INTERFACE_APP_URL=xxx                    # interface 服务地址
INTERFACE_APP_INTERNAL_TOKEN=xxx         # engine 调用 interface 的 token
APP_INTERNAL_VALIDATION_SKIP=1           # 本地开发跳过内部鉴权
BKFLOW_CELERY_BROKER_URL=amqp://...
```

## 双模块数据库约束

- interface 和 engine 各有独立的数据库，不共享
- engine 模块 `isolation_level=all_resource` 时使用完全独立的 DB 配置
- `local_settings.py` 中需判断模块类型配置对应 DB：

```python
if BKFLOW_MODULE_TYPE != BKFLOWModuleType.engine.value \
        or BKFLOW_MODULE.isolation_level != "all_resource":
    DATABASES = {"default": {...}}  # interface DB
```

## Celery Worker 启动配置

### interface 模块

```bash
celery -A blueapps.core.celery worker -n interface_worker@%h -P threads -c 100 -l info
celery -A blueapps.core.celery beat -l info
```

### engine 模块

需要三个独立 Worker（`${BKFLOW_MODULE_CODE}` 为实际模块 code）：

```bash
# 通用任务队列
celery worker -Q celery,pipeline_additional_task,...,task_common_${CODE},node_auto_retry_${CODE},... \
  -n common_worker@%h -P threads -c 10

# 调度队列
celery -A blueapps.core.celery worker -P threads -Q er_schedule_${CODE} \
  -n er_s_worker@%h -c 100

# 执行队列
celery -A blueapps.core.celery worker -P threads -Q er_execute_${CODE} \
  -n er_e_worker@%h -c 100

celery -A blueapps.core.celery beat -l info
```

## SDK 包管理

BKFlow 维护的关键 SDK，使用 flit 工具 build 后发布到内网 PyPI 源。

### Python 3.12 升级注意事项

- 参考 PR：BKFlow#354，同步升级了所有 SDK
- bamboo-engine、bkflow-django-webhook 均有对应 PR
- 容器化部署 Dockerfile 基于 Python 3.12-slim

## 容器化部署关键约束

- **前端静态文件路径**：构建产物放入 `./static/bkflow`，启动脚本复制到 `./staticfiles/bkflow`
- **启动脚本判断**：`BKPAAS_APP_MODULE_NAME == "default"` 时执行 SaaS 初始化（`sync_saas_apigw`、`sync_superuser`、`sync_default_module` 等）
- **Gunicorn 配置**：默认 4 workers，2 threads/worker，端口 5000，支持 IPv6（`[::]:PORT`）
- **静态文件目录**：`STATICFILES_DIRS` 需配置能找到 `static/bkflow` 的路径

## 代码初始化约束

本地首次启动需手动执行：

1. 在 Django Admin 中配置当前空间对应的 engine 后端（interface 服务启动后）
2. 将登录账号配置为超级管理员
3. 复制前端模板文件：

```bash
cp ./staticfiles/bkflow/index-prod.html ./bkflow/interface/templates/base_vue.html
```

## 业务扩展方式

接入系统可通过以下方式扩展 BKFlow 能力：

- **蓝鲸插件**：通过蓝鲸开发者中心开发，BKFlow 自动同步
- **API 插件**：暴露符合协议的接口，在空间配置 `uniform_api` 注册
- **Webhook 订阅**：调用 `apply_webhook_configs` API 订阅事件，BKFlow 在事件触发时回调
