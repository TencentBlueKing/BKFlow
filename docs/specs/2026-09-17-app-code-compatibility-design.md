# 出包规范整改与上云存量部署兼容

## 目标与适用范围

社区、BKOP、SG 的标准 Smart 包使用 `bk_flow`。上云已有应用保留其平台登记的 app_code、凭证、网关及模块地址，使用同一份代码升级。

本次覆盖 APP_Code、平台协议、时区、凭证算法、管理员授权、双语文档和版本声明七项已确认缺口。既有空间绑定、审批工作流 key 和 Engine 路由记录保持兼容。原评估中需要真实制品、目标环境或运营流程证据的项目仍须验收。

[English deployment guide](../guide/release_compatibility_en.md)

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

## 四、平台协议与存量服务

在 Interface 和每个 Engine 上设置相同的协议模式：

| 环境 | `BKFLOW_PLATFORM_API_MODE` | 租户模式 | 行为 |
| --- | --- | --- | --- |
| 新社区单租户 | `apigw`（默认） | 关闭 | 使用 default 租户的 CMSI、用户管理、ITSM4 |
| 新多租户 | `apigw` | 开启 | 按真实租户调用 APIGW；即使误配 legacy 也不会回退 ESB |
| 旧上云单租户 | `legacy` | 关闭 | 保留旧 ESB 通知、人员选择、语言偏好及审批创建协议 |

新平台通过 `BK_API_URL_TMPL` 和 `BK_APIGW_STAGE_NAME` 定位 `bk-cmsi`、`bk-user-web`、`bk-login`、`bk-itsm4`；部署方须配置真实地址和应用授权。语言偏好使用 bk-user-web 的 `PUT /api/v3/open-web/tenant/current-user/language/`，携带用户登录态与 `X-Bk-Tenant-Id`。

新平台单租户启用审批前，在 Interface 执行 `python manage.py init_tenant --tenant_id default`；多租户使用实际租户 ID。该命令调用远端 ITSM4，必须在目标平台完成授权后执行并检查结果，重复执行/失败恢复仍需要远端验收。旧模式继续沿用原 ITSM 初始化方式和 `BK_ITSM_API_ENTRY`。已产生的审批单按输出中的旧 `sn` 或新 `id` 选择处理协议，切换到新平台后若仍处理旧单，必须保留指向旧 ITSM 兼容服务的 `BK_ITSM_API_ENTRY`。新平台模式不会隐式拼接 ESB 地址。

旧上云部署的最小兼容配置示例（Interface 与每个 Engine）：

```bash
BKFLOW_PLATFORM_API_MODE=legacy
BKFLOW_CREDENTIAL_CIPHER=AES
# 保留原租户开关、平台注入身份、PRIVATE_SECRET 和内部认证 token
# BK_ITSM_API_ENTRY、BK_PAAS_ESB_HOST 等仍沿用目标环境原值
```

## 五、时区与国密凭证

时区按以下顺序选择有效 IANA 时区：内部 `Bkflow-Internal-Time-Zone`、标准 `blueking-timezone`、`blueking_timezone` Cookie、同名 session、新平台用户时区、部署 `TIME_ZONE`。单/多租户规则一致，非法值忽略；旧平台无显式偏好时保持部署默认值。内部模块传递继续使用原专用请求头。定时触发器新建时将当前用户时区保存到 `config.timezone` 并传给 Engine；编辑省略该字段时保留原值。历史未标时区的计划保留 Engine 中已有的 crontab 时区，避免更换编辑者后漂移；页面显示新计划时区并据此预览。

凭证算法由 `BKFLOW_CREDENTIAL_CIPHER=AES|SM4` 控制，默认 AES，旧 AES 密文格式不变。SM4 使用蓝鲸 Python SDK 2.0.1 的 SM4-GCM；密文带版本前缀和随机 nonce，可校验篡改。新代码根据密文标识读取两种格式，写入算法不限制读取算法。历史迁移依赖的 `BaseCrypt` 不修改。

启用步骤：

1. 保持原 `PRIVATE_SECRET`，先以 AES 配置升级所有凭证读写模块，验证原凭证可读取。
2. 确认所有模块已支持新格式后，统一设置 `BKFLOW_CREDENTIAL_CIPHER=SM4`；此后新增/更新凭证写入 SM4，历史记录不自动批量重写。
3. 若交付要求所有历史凭证都为国密，须在目标环境备份后重新保存相应凭证并验收；仅切换配置不会转换已有 AES 数据。
4. 切回 AES 只改变后续写入，新代码仍能读取 SM4。存在 SM4 数据后，不可直接回滚到本次改动之前的代码；需先用新代码转回 AES 并核验，或恢复相配套的备份。密钥轮换也需独立迁移。

本项修复的是 `Credential.content` 的业务存储路径；不将其等同于整套系统、第三方库及目标环境已完成国密认证。

## 六、管理员授权

多租户使用 `sync_superuser` 授权前，目标用户须先登录以同步真实租户身份。仅允许已存在且 `tenant_id=system` 的用户：

```bash
python manage.py sync_superuser --usernames <system用户名>
```

发布步骤原有的 `BKFLOW_INIT_SUPERUSERS` 仍可使用；其中任一用户不存在或不属于 system，整批拒绝并使发布步骤失败。不要在首次部署时填入尚未登录的用户；完成登录后手动授权。此命令只授权，不自动撤销历史已存在的超管；开启多租户前应核对并清理不符合新约定的旧授权。单租户仍保留原创建/更新管理员行为。

业务管理员映射到 BKFlow 的**空间管理员**，按明确的租户和空间授权：

```bash
python manage.py grant_space_admin --username <用户名> --tenant-id <租户ID> --space-id <空间ID>
```

用户须已登录且有效，空间须存在；多租户中用户与空间必须同属指定租户。单租户仅允许 default。命令幂等追加空间的 `superusers` 配置，不设置 Django 超管标志，也不授予同租户其他空间权限。多租户原生 Django admin 的禁用策略保持不变。

## 七、版本与双语交付

本次源码版本为 `1.11.14`，中英文日志记录 `V1.11.13` 到当前 master 及本次整改的差异。旧标签不移动；合入后由发布流程创建新标签，并记录构建 SHA、Smart 包和镜像摘要。本 PR 不代表标签或制品已经发布。

新增英文 README、94 篇与中文接口同名的英文 API 文档及当前版本日志；`scripts/apigw_docs.sh` 同时打包 `zh/` 和 `en/`。接口样例保留原业务示例值，以便比较请求/响应结构。

帮助入口优先读取 `BKFLOW_DOC_URL_ZH` / `BKFLOW_DOC_URL_EN`。未指定完整 URL 时，可设置已实际发布的 `BKFLOW_DOC_VERSION`，结合 `BK_DOC_CENTER_HOST` 生成文档中心地址。都未配置时使用仓库当前指南/英文 README，不再固定到 1.8。私有化环境应配置其可访问的文档地址，不能假定外网 GitHub 可达。

## 验证与发布检查

本地测试覆盖：

- `bk_flow`、`bk_flow_engine`、中划线旧名称在 Interface/Engine 的身份和服务发现。
- 显式网关名、空网关配置、旧命名转换，以及不同域名/子路径的地址覆盖优先级。
- 标准与上云专用描述生成、自身/外部服务发现引用、源文件保护及非法配置拒绝。

配置测试使用替身和独立进程，业务回归使用隔离测试库，不连接真实平台。部署前后还应核验：

1. 打包描述与目标 PaaS 应用身份一致；原应用、数据库、凭证和用户授权保留。
2. `sync_saas_apigw` 的实际目标是原网关，后端域名和子路径正确；检查资源、授权及回调地址。
3. Interface 到各 Engine、各 Engine 到 Interface、在途回调及插件服务调用正常。
4. 核对通知注册、插件分发方和既有 ITSM 系统绑定继续使用原应用身份。

新增实现不包含 schema 迁移，但基线已合入的多租户升级仍须对 Interface、每个 Engine 及统计库执行各自迁移，不能跨库直接读取 Interface 数据。未写入 SM4 时可使用原代码/制品和原环境配置回滚；写入 SM4 后按上述凭证回滚限制处理。若部署时主动改变平台应用身份或网关，应另行制定迁移与回滚方案，不能按本次兼容升级处理。


发布验收仍需提交：准确 SHA 对应的 Smart 制品/镜像和流水线记录、子路径与 IPv6 连通性、两种租户模式和非上海时区的界面/接口/周期任务、审批与通知、登录续期及全局注销、依赖缺失提示、探针、CodeCC/敏感扫描与安全工单、BKOP 稳定运行及交付会签。源码整改和本地回归不替代这些证据。
