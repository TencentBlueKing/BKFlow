---
name: bkflow-dev-guide
description: Use when setting up BKFlow development environment, deriving Python and Node requirements from project config, working with the interface/engine dual-module local setup, starting local web with runserver plus hosts mapping, or understanding deployment constraints.
---

# BKFlow 开发指南

## Overview

BKFlow 采用 `interface + engine` 双模块架构。本地开发时，优先通过项目内已有配置推导依赖版本和启动方式，不在文档里写死个人机器配置、共享组件地址或敏感凭据。

## 依赖版本以项目配置为准

本地安装 Python / Node 时，优先读取仓库中的项目配置，而不是手工记忆版本号。

### Python

- 版本来源：[`runtime.txt`](/Users/dengyh/Projects/bk-flow/runtime.txt)
- 安装工具可使用 `pyenv`
- 虚拟环境可使用 `uv + direnv`

示例：

```bash
PYTHON_VERSION="$(sed 's/^python-//' runtime.txt)"
pyenv install -s "${PYTHON_VERSION}"
uv venv --python "${PYTHON_VERSION}" .venv
uv pip install -r requirements.txt
```

### Node.js

- 版本来源：[`frontend/package.json`](/Users/dengyh/Projects/bk-flow/frontend/package.json) 中的 `engines.node`
- 安装工具可使用 `nvm`
- 包管理器按仓库锁文件使用 `npm`

示例：

```bash
NODE_RANGE="$(node -p "require('./frontend/package.json').engines.node")"
echo "${NODE_RANGE}"
cd frontend
npm install
```

## 推荐的本地 Python 工作流

本地开发推荐使用：

- `pyenv` 管 Python 版本
- `uv` 管虚拟环境和依赖
- `direnv` 负责进入目录自动激活 `.venv`

项目根目录建议维护本地文件：

- `.python-version`
- `.envrc`

其中 `.envrc` 只做本地加载，不进入版本库。可以保持为：

```bash
dotenv_if_exists .env
layout_uv .venv "$(sed 's/^python-//' runtime.txt)"
```

如果需要额外的私有 PyPI 源或本地代理，也放在 `.envrc` 或 shell 环境里，不写入共享文档。

## 本地域名与 hosts

本地启动 interface 时，尽量使用域名方式而不是直接绑定 `127.0.0.1`，并在 `hosts` 中加入映射。

推荐示例：

```text
127.0.0.1 local.bk-dev.woa.com
```

对应启动命令：

```bash
python manage.py runserver local.bk-dev.woa.com:8000
```

如果本地还要同时启动 engine，也建议使用独立的本地域名和端口，并保持 interface / engine 之间的回调地址一致。

## 前端构建与本地 Web

本地 web 默认使用编译好的前端产物，不以 webpack dev server 作为主入口。

在 `frontend/` 目录执行：

```bash
cd frontend
npm install
npm run build
mkdir -p ../staticfiles/bkflow
cp -rf static/* ../staticfiles/bkflow
```

本地首次准备前端模板时，还需要：

```bash
mkdir -p ./bkflow/interface/templates
cp ./staticfiles/bkflow/index-prod.html ./bkflow/interface/templates/base_vue.html
```

## interface / engine 的关键环境变量

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
APP_INTERNAL_TOKEN=xxx                   # 内部 API 鉴权 token，本地自行注入
BKAPP_DEFAULT_ENGINE_MODULE_ENTRY=xxx    # engine 服务地址，建议使用本地域名
DEFAULT_ENGINE_APP_INTERNAL_TOKEN=xxx    # interface 调用 engine 的 token，本地自行注入
BKFLOW_CELERY_BROKER_URL=amqp://...
```

### engine 模块关键变量

```bash
BKFLOW_MODULE_TYPE=engine
BKFLOW_MODULE_CODE=xxx
DB_NAME=bkflow-default-engine
BKFLOW_DATABASE_NAME=bkflow-default-engine
INTERFACE_APP_URL=xxx                    # interface 服务地址，建议使用本地域名
INTERFACE_APP_INTERNAL_TOKEN=xxx         # engine 调用 interface 的 token，本地自行注入
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

## `local_settings.py` 的使用原则

`local_settings.py` 只负责本地覆盖，不要写入团队共享的真实地址、账号或密码。常见本地覆盖项包括：

- `STATIC_ROOT`
- `DATABASES`
- `REDIS`
- 本地权限或网关开关
- `AUTORELOAD`

可以使用环境变量占位：

```python
import os

STATIC_ROOT = "staticfiles"
BK_APIGW_REQUIRE_EXEMPT = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "bkflow-interface"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
    },
}

REDIS = {
    "host": os.getenv("REDIS_HOST", "127.0.0.1"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "password": os.getenv("REDIS_PASSWORD", ""),
}
```

## 本地初始化步骤

首次启动 interface 时，通常需要执行：

```bash
python manage.py collectstatic --noinput
python manage.py migrate
```

完成后还需要做两件事：

1. 在 Django Admin 中配置当前空间对应的 engine 后端
2. 将当前登录账号设为超级管理员

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

## 本地启动建议

### interface

优先使用：

```bash
python manage.py runserver local.bk-dev.woa.com:8000
```

### engine

engine 同理使用本地域名启动，并确保：

- `INTERFACE_APP_URL` 指向本地 interface
- `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY` 指向本地 engine
- `BKFLOW_MODULE_CODE` 与对应 celery 队列保持一致

### 调试时的补充建议

- 本地 web 默认走编译后的前端页面
- 如果要核对静态资源，检查 `/static/bkflow/...`
- 如果需要直接用 gunicorn 验证问题，在 macOS 上优先使用 `-k sync`

## SDK 包管理

BKFlow 维护的关键 SDK，使用 flit 工具 build 后发布到内网 PyPI 源。

## 容器化部署关键约束

- **前端静态文件路径**：构建产物放入 `./static/bkflow`，启动脚本复制到 `./staticfiles/bkflow`
- **启动脚本判断**：`BKPAAS_APP_MODULE_NAME == "default"` 时执行 SaaS 初始化（`sync_saas_apigw`、`sync_superuser`、`sync_default_module` 等）
- **Gunicorn 配置**：默认 4 workers，2 threads/worker，端口 5000，支持 IPv6（`[::]:PORT`）
- **静态文件目录**：`STATICFILES_DIRS` 需配置能找到 `static/bkflow` 的路径

## 业务扩展方式

接入系统可通过以下方式扩展 BKFlow 能力：

- **蓝鲸插件**：通过蓝鲸开发者中心开发，BKFlow 自动同步
- **API 插件**：暴露符合协议的接口，在空间配置 `uniform_api` 注册
- **Webhook 订阅**：调用 `apply_webhook_configs` API 订阅事件，BKFlow 在事件触发时回调

---

## 本地常见问题排查

### 问题一：登录后一直重定向回登录页

**现象**：在 `http://local.bk-dev.woa.com:8000/` 登录后，页面不断跳回登录页。

**根因**：`bk_token` 验证失败，通常是以下原因之一：

#### 原因 A：`BKPAAS_LOGIN_URL` 配置错误

登录服务地址配置不对，导致 `bk_token` Cookie 的 domain 与本地服务不匹配，或者 `verify_bk_token_through_verify_url` 请求的地址不正确。

**解决**：在 `.env` 里配置正确的登录服务地址：

```bash
BKPAAS_LOGIN_URL=http://<BK_LOGIN_DOMAIN>/
BK_LOGIN_INNER_URL=http://<BK_LOGIN_DOMAIN>/login/
```

`BK_LOGIN_INNER_URL` 控制 `verify_bk_token_through_verify_url` 实际请求的地址，格式为 `http://<BK_LOGIN_DOMAIN>/login/`。

#### 原因 B：ESB `is_login` 接口报 `must specify the request method`

`client.bk_login.is_login` 是 custom api，没有预定义 HTTP 方法，调用时会抛出异常并 fallback 到 `verify_bk_token_through_verify_url`（直接 HTTP 请求登录服务）。这是**正常的降级行为**，不影响最终验证结果，只要 `BK_LOGIN_INNER_URL` 配置正确即可。

#### 原因 C：`get_user_info` 失败（ESB `get_user` 接口不可用）

`verify_bk_token` 成功后，还会调用 `client.bk_login.get_user` 获取用户信息。如果 ESB 不支持这个接口，会返回 `False`，导致 `authenticate` 返回 `None`。

**排查方法**：在后台日志里看到以下输出时，说明是这个问题：

```
[DEBUG] get_user_info_result=False, user_info={}
[DEBUG] get_user_info failed, return None
```

**解决**：这是 ESB 环境侧的问题。本地开发可以在 `.venv` 里的 `backends.py` 临时 patch，让 `get_user_info` 失败时不阻断登录（token 验证已成功，直接返回 user）。

---

### 问题二：创建空间时报 `API not found [path="/bkpaas3/prod/system/uni_applications/query/by_id/"]`

**现象**：非超级管理员用户创建空间时，调用 PaaS3 的 `uni_applications` 接口报 404。

**根因**：`PAASV3_APIGW_API_HOST` 配置的地址不正确，或者 APIGW 上没有注册 `bkpaas3` 网关。

**排查**：先确认你的环境里 APIGW 的路径格式。不同环境的路径格式不同：

- 标准格式：`http://<BK_APIGW_DOMAIN>/{api_name}/...`
- 带 `/api` 前缀：`http://<BK_APIGW_DOMAIN>/api/{api_name}/...`

可以用 curl 验证：

```bash
# 测试不带 /api 前缀
curl "http://<BK_APIGW_DOMAIN>/bkpaas3/prod/system/uni_applications/query/by_id/?id=<app_code>"

# 测试带 /api 前缀
curl "http://<BK_APIGW_DOMAIN>/api/bkpaas3/prod/system/uni_applications/query/by_id/?id=<app_code>"
```

**解决**：根据实际路径格式配置 `.env`：

```bash
# 如果 APIGW 路径带 /api 前缀
PAASV3_APIGW_API_HOST=http://<BK_APIGW_DOMAIN>/api/bkpaas3

# 同时修正 NETLOC 正则（原来的 ^bkapi.{hostname} 是占位符，不是有效正则）
BK_APIGW_NETLOC_PATTERN=^<BK_APIGW_DOMAIN_ESCAPED>
```

**注意**：`PAASV3_APIGW_API_HOST` 在 `config/default.py` 里由 `BK_APIGW_URL_TMPL` 动态生成，如果在 `.env` 里直接设置，需要确认 `env.py` 里的加载顺序，`.env` 里的值可能被 `config/default.py` 的计算结果覆盖。如果遇到这种情况，在 `local_settings.py` 里直接覆盖：

```python
PAASV3_APIGW_API_HOST = "http://<BK_APIGW_DOMAIN>/api/bkpaas3"
```

---

### 问题三：`env.py` 里的环境变量未生效

**现象**：在 `.env` 里配置了某个变量（如 `PAASV3_APIGW_API_HOST`），但服务运行时读到的还是旧值。

**根因**：`config/default.py` 里部分变量是通过计算动态生成的，会覆盖 `.env` 里的直接赋值。例如：

```python
# config/default.py
PAASV3_APIGW_API_HOST = env.BK_APIGW_URL_TMPL.format(
    api_name="paasv3" if env.BKPAAS_ENGINE_REGION == "ieod" else "bkpaas3"
)
```

**解决**：在 `local_settings.py` 里直接覆盖，`local_settings.py` 在 `config/default.py` 之后加载，优先级更高：

```python
# local_settings.py
PAASV3_APIGW_API_HOST = "http://<BK_APIGW_DOMAIN>/api/bkpaas3"
```
