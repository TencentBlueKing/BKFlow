# 安全加固升级说明

本次加固包含五项改动：Python 代码节点沙箱收紧、移除 `app_desc.yaml` 中的默认密钥、APIGW 来源识别改为完整匹配主机名、
周期任务接口要求内部调用凭证、校验跳过开关改为严格布尔解析。升级前需要先按下文注入密钥，否则发布会在迁移前停止。

## 发布前注入密钥

`app_desc.yaml` 不再携带可用的默认密钥，以下配置需要在开发者中心的环境变量中注入：

| 模块 | 环境变量 | 取值要求 |
|------|----------|----------|
| default（接口模块） | `APP_INTERNAL_TOKEN` | 接口模块自己的内部调用 token |
| default（接口模块） | `DEFAULT_ENGINE_APP_INTERNAL_TOKEN` | 与 default-engine 的 `APP_INTERNAL_TOKEN` 相同，不超过 32 个字符 |
| default-engine | `APP_INTERNAL_TOKEN` | 引擎模块自己的内部调用 token，不超过 32 个字符 |
| default-engine | `INTERFACE_APP_INTERNAL_TOKEN` | 与接口模块的 `APP_INTERNAL_TOKEN` 相同 |
| 两个模块 | `BKFLOW_DEFAULT_CALLBACK_KEY` | 同一个 Fernet 密钥，接口模块解密回调链接，引擎模块生成回调链接 |

生成方式：

```bash
# 内部调用 token（32 个字符）
python -c "import uuid; print(uuid.uuid4().hex)"
# 回调密钥
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

32 个字符的限制来自模块信息表（`ModuleInfo.token`）的字段长度。独立部署的其他引擎模块同样需要注入自己的
`APP_INTERNAL_TOKEN`、`INTERFACE_APP_INTERNAL_TOKEN` 和 `BKFLOW_DEFAULT_CALLBACK_KEY`。

### 替换旧版本公开过的取值

旧版本 `app_desc.yaml` 中提交过以下默认值，它们已随源码公开。环境中仍在使用时必须替换：

- 接口模块 `APP_INTERNAL_TOKEN` / 引擎模块 `INTERFACE_APP_INTERNAL_TOKEN`：以 `df1da1fc` 开头的 32 位十六进制串。
- `DEFAULT_ENGINE_APP_INTERNAL_TOKEN` / default-engine `APP_INTERNAL_TOKEN`：以 `a35230d7` 开头的 32 位十六进制串。
- `BKFLOW_DEFAULT_CALLBACK_KEY`：以 `jbSH1_3P` 开头的 Fernet 密钥。

完整取值可在本次改动之前的 `app_desc.yaml` 历史版本中核对。

### 存量数据库中的默认引擎记录

重新部署不会改动已登记的默认引擎模块（`ModuleInfo`，`space_id=0`）。`sync_default_module` 只在记录不存在时创建，
已有记录的 token 和入口地址保持不变。

因此轮换 default-engine 的 token 时，需要同时完成两件事：

1. 更新 default-engine 的 `APP_INTERNAL_TOKEN` 和接口模块的 `DEFAULT_ENGINE_APP_INTERNAL_TOKEN`。
2. 在管理端或数据库中把 `ModuleInfo(space_id=0).token` 改为同一个值。

两者不一致时，接口模块调用引擎会被拒绝。发布检查发现环境变量与已登记值不同时只输出告警，不阻止发布。

### 轮换回调密钥

节点回调链接使用 `BKFLOW_DEFAULT_CALLBACK_KEY` 加密。轮换后，已发放给外部系统、尚未回调的链接将无法解密。
建议在没有等待回调节点的窗口期切换，或切换后人工处理仍在等待的节点。

### 发布检查

`bin/pre_release.sh` 在执行迁移前运行 `python manage.py check_deploy_secrets`，检查失败时不改动数据库。检查内容：

- 两个模块都配置了 `APP_INTERNAL_TOKEN`，`BKFLOW_DEFAULT_CALLBACK_KEY` 是有效的 Fernet 密钥。
- 引擎模块的 `APP_INTERNAL_TOKEN` 不超过 32 个字符，并配置了 `INTERFACE_APP_INTERNAL_TOKEN`。
- 接口模块尚未登记默认引擎时，需要配置 `DEFAULT_ENGINE_APP_INTERNAL_TOKEN`（不超过 32 个字符）和
  `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY`；已登记时沿用存量记录。

错误信息只列出缺失的配置项名称，不输出取值。`RUN_MODE=DEVELOP` 的本地开发环境跳过该检查。

### 发布后滚动重启 er-e

旧版本的 Python 代码节点会在 er-e 进程中降低资源硬限制，进程无法自行恢复。发布新版本后需要滚动重启现有 er-e Pod。

## Python 代码节点

### 默认关闭

Python 代码节点（`python_code`）默认关闭，开启需要在两个模块都配置 `PYTHON_CODE_PLUGIN_ENABLED=true`：

- 接口模块：控制节点是否对所有空间可见。关闭时节点加入空间插件白名单控制（`SPACE_PLUGIN_LIST`），
  只有在空间插件配置中加入 `python_code` 的空间可以看到。
- 引擎模块：控制节点是否真正执行代码。关闭时节点直接失败，提示
  `Python代码节点未开启，请联系平台管理员在引擎模块配置 PYTHON_CODE_PLUGIN_ENABLED 后重试`。

已使用该节点的存量流程在开启前运行到该节点会失败，升级前请先确认是否有存量使用。开启后可以对失败节点重试。

### 模块白名单

开启节点后，用户代码默认不能使用任何模块。在引擎模块配置 `PYTHON_CODE_PLUGIN_ALLOWED_MODULES` 开放需要的模块：

```bash
# 逗号分隔
PYTHON_CODE_PLUGIN_ALLOWED_MODULES=json,math,datetime
# 或开放全部可选模块
PYTHON_CODE_PLUGIN_ALLOWED_MODULES=*
```

可选模块：`json`（以 `json_dumps`、`json_loads` 提供）、`jsonschema`（以 `jsonschema_module` 提供）、`math`、`statistics`、
`decimal`、`fractions`、`datetime`、`collections`、`itertools`、`functools`、`string`、`textwrap`、`base64`、`hashlib`、
`hmac`、`uuid`、`copy`。其他名称会被忽略，并在节点日志中告警。

### 开放模块后仍不可用的成员

开放的模块只提供公开成员，并去掉子模块（如 `uuid.os`、`fractions.sys`）。以下成员可以读取函数全局变量、
执行注解字符串或绕过格式化限制，也不提供：

| 模块 | 不可用成员 |
|------|------------|
| `collections` | `UserString` |
| `copy` | `dispatch_table` |
| `datetime` | `datetime_CAPI` |
| `functools` | `singledispatch`、`singledispatchmethod`、`update_wrapper`、`wraps` |
| `string` | `Formatter` |

`jsonschema_module` 只提供 `validate`、`ValidationError` 和 `SchemaError`。未声明 `$schema` 时按 Draft 4 校验，
与旧版本一致；只解析当前 schema 内的引用（如 `#/definitions/x`），远程或文件 `$ref` 直接报错，不会发起请求。
`validators`、`Draft7Validator` 等其他成员不再提供。

### 子进程隔离

用户代码在独立子进程中执行，子进程只继承 `PATH`、`TZ` 和编码相关的环境变量，不再继承密钥和数据库配置；
执行前关闭继承的文件描述符，并限制可创建的进程数和可打开的文件数。

### 已知问题

`datetime` 对象的 `strftime()` 在沙箱中会报 `'__import__'` 错误，升级前的版本同样存在，不是本次改动引入。
可暂用 `isoformat()` 或手动拼接字段代替。

## APIGW 来源识别

`BK_APIGW_NETLOC_PATTERN` 改为完整匹配请求地址的主机名（不含端口），带用户名或密码的地址一律视为非 APIGW 地址。
默认值改为 `^bkapi\.{hostname}$`，`{hostname}` 会替换为转义后的 `BKPAAS_DOMAIN`。自定义该变量时，请确认正则只描述主机名，
不包含端口或路径。携带网关签名的请求不再跟随重定向。

## 周期任务接口

引擎模块的周期任务接口只接受平台超级管理员或携带有效内部调用 token 的请求。接口模块通过已登记的模块 token 调用，
无需额外配置；直接访问引擎周期任务接口的其他调用方需要改为经接口模块转发。

## 校验跳过开关

`APP_INTERNAL_VALIDATION_SKIP`（跳过内部调用 token 校验）和 `SKIP_APIGW_CHECK`（跳过 APIGW 来源识别）改为严格解析：
只有 `1`、`true`、`yes`、`on`（不区分大小写）表示开启，其他取值都表示关闭。

旧版本只要变量非空就会开启，配置为 `0`、`false` 时也会跳过校验。升级后这些取值会恢复校验；若环境中确实需要跳过
（仅限本地开发或测试），请改为 `true`。生产环境不应开启这两个开关。
