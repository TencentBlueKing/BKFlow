# APP_Code 规范与上云存量部署兼容

## 目标与适用范围

社区、BKOP、SG 的标准 Smart 包使用 `bk_flow`。上云已有应用保留其平台登记的 app_code、凭证、网关及模块地址，使用同一份代码升级。

本次调整应用标识和打包配置，未改变数据库、租户归属、空间绑定、已有审批工作流 key 或业务 Engine 路由记录。ESB、时区、国密等其他出包要求需分别完成。

## 标识与配置优先级

| 用途 | 配置来源 | 默认行为 |
| --- | --- | --- |
| 标准 Smart 包的应用标识 | `app_desc.yaml` 的 `app.bk_app_code` | `bk_flow` |
| 上云专用 Smart 包的应用标识 | 打包阶段的 `BKFLOW_PACKAGE_APP_CODE` | 未配置或为空时保留源描述值；自动更新自身服务发现引用 |
| 上云专用 Smart 包中的网关配置 | 打包阶段的 `BKFLOW_PACKAGE_APIGW_NAME` | 非空时写入 default 模块的 `BK_APIGW_NAME`；未配置时由运行时决定 |
| 运行时应用认证身份 | PaaS 注入 `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET` | 持续使用平台实际应用的身份，不从 app_desc.yaml 覆盖 |
| BKFlow 网关名称 | 运行时 `BK_APIGW_NAME` | 非空显式配置优先；否则采用 `BKPAAS_APP_ID`；沿用下划线转中划线规则 |
| 自身模块服务发现 | PaaS 注入 `BKPAAS_SERVICE_ADDRESSES_BKSAAS` | 根据实际 `BKPAAS_APP_ID` 和模块名查询，按部署环境取地址 |
| 插件分发方 | `PLUGIN_DISTRIBUTOR_NAME` / `BKAPP_PLUGIN_DISTRIBUTOR_NAME` | 保留原优先级；未配置时为实际 APP_CODE |

例如，新应用 `bk_flow` 的默认网关名为 `bk-flow`；旧应用 `bk_flow_engine` 的默认网关名仍为 `bk-flow-engine`。如果实际存量网关名称不同，必须显式配置 `BK_APIGW_NAME`，避免发布步骤同步到另一个网关。

包内不再固定注入 `BK_APIGW_NAME=bk_flow`，以免标准包默认值覆盖目标环境的网关选择。`BKFLOW_PACKAGE_*` 只在下面的描述生成脚本中生效，PaaS 和运行时不会自动展开这些变量。

## 一、标准 Smart 包

直接使用仓库的 `app_desc.yaml` 即可。应用标识为 `bk_flow`，default 与 default-engine 的自身发现引用一致，外部用户管理服务引用保持原值。

如果流水线统一采用生成步骤，可以执行：

```bash
python scripts/render_app_desc.py --output /tmp/bkflow-package/app_desc.yaml
```

生成步骤依赖 PyYAML，仓库的运行依赖环境已包含此库；精简打包环境需预先安装。输出文件应作为 Smart 包根目录的 `app_desc.yaml`，源码仍按原流水线复制到 `src/`。该脚本只生成描述，不创建完整制品、不上传包、不部署应用。

## 二、上云源码部署到存量应用

在**原有 PaaS 应用**中更新源码，保留平台登记身份和已有密钥。运行时持续读取平台注入的 `BKPAAS_APP_ID`，例如 `bk_flow_engine` 或已有中划线名称。

在 Interface 的 default 模块检查以下运行时环境变量；已有值继续保留，具体值以目标环境为准：

```bash
# 示例：替换成目标环境已有的网关名
BK_APIGW_NAME=legacy-bkflow-gateway

# 仅在自动服务发现不适用时设置，保留真实子路径
BKAPP_APIGW_API_HOST=https://interface.example.com/bkflow/
BKAPP_INNER_CALLBACK_ENTRY=https://interface.example.com/bkflow/
BKAPP_DEFAULT_ENGINE_MODULE_ENTRY=https://engine.example.com/bkflow/
```

| 变量 | 作用和优先级 | 使用模块 |
| --- | --- | --- |
| `BKAPP_APIGW_API_HOST` | APIGW 后端地址，优先于自身 default 模块发现；保留 URL 子路径 | Interface |
| `BKAPP_INNER_CALLBACK_ENTRY` | 内部回调地址，优先于自身 default 模块发现 | 产生回调地址的模块，通常是 Engine；按需在所有相关模块配置 |
| `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY` | 默认 Engine 地址，优先于自身 default-engine 模块发现 | Interface 的默认模块初始化 |
| `INTERFACE_APP_URL` | Engine 调用 Interface 的地址，优先于自身 default 模块发现；去除末尾 `/` | 每个 Engine |
| `INTERFACE_APP_INTERNAL_TOKEN` | Engine 调用 Interface 的认证 token，须匹配目标 Interface | 每个 Engine |
| `DEFAULT_ENGINE_APP_INTERNAL_TOKEN` | 初始化默认 Engine 记录使用的 token，须匹配目标 Engine | Interface |
| `APP_INTERNAL_TOKEN` | 本模块接受内部调用的 token，保留既有值 | Interface 和每个 Engine |

对单独部署的业务 Engine，应在每个应用/模块上保留 `INTERFACE_APP_URL` 及对应认证配置。显式配置地址时应使用真实可达的存量服务 URL，不把包内默认名称当作路由地址。

`sync_default_module` 只在记录缺失时创建默认 Engine，不会覆盖已有 ModuleInfo 的 URL/token。设置 `BKAPP_DEFAULT_ENGINE_MODULE_ENTRY` 不会自动改写存量记录；发布前应只读核对已有记录仍指向原服务。确需迁移地址时，应按独立的路由变更流程处理。

## 三、上云使用 Smart 包升级存量应用

Smart 包的应用标识在导入阶段就参与应用识别，不能等包导入后仅修改 `BKPAAS_APP_ID` 来兼容旧应用。应在原流水线的压缩归档前生成与存量应用一致的描述：

```bash
BKFLOW_PACKAGE_APP_CODE=bk_flow_engine \
BKFLOW_PACKAGE_APIGW_NAME=legacy-bkflow-gateway \
python scripts/render_app_desc.py --output /tmp/bkflow-package/app_desc.yaml
```

两个示例值均需替换成目标环境已有的登记值；保留中划线 app_code 时也使用原值。生成器同步修改自身模块的 `svc_discovery.bk_saas` 引用，保持其他服务引用不变。源描述不会被覆盖，不能把生成结果提交回标准 `app_desc.yaml`。

将生成文件纳入包根目录后再沿用原流水线归档、导入和部署，并核对导入目标仍是原应用。源码构建无需设置这两个打包变量。

## 验证与发布检查

本地测试覆盖：

- `bk_flow`、`bk_flow_engine`、中划线旧名称在 Interface/Engine 的身份和服务发现。
- 显式网关名、空网关配置、旧命名转换，以及不同域名/子路径的地址覆盖优先级。
- 标准与上云专用描述生成、自身/外部服务发现引用、源文件保护及非法配置拒绝。

本地配置测试不连接真实平台、网关或数据库。部署前后还应核验：

1. 打包描述与目标 PaaS 应用身份一致；原应用、数据库、凭证和用户授权保留。
2. `sync_saas_apigw` 的实际目标是原网关，后端域名和子路径正确；检查资源、授权及回调地址。
3. Interface 到各 Engine、各 Engine 到 Interface、在途回调及插件服务调用正常。
4. 核对通知注册、插件分发方和既有 ITSM 系统绑定继续使用原应用身份。

回滚使用原代码/制品和原环境配置；本次无数据库迁移。若部署时主动改变平台应用身份或网关，应另行制定迁移与回滚方案，不能按本次兼容升级处理。
