# 真实 HTTP 节点联调准备包

这个独立测试服务用于验证 BKFlow 的真实 HTTP 插件和节点间参数传递。网络请求和参数渲染是真实的，业务数据是合成的。它不代表生产服务检查，也不连接数据库、网关管理接口或通知服务。

## 已准备

- `service.py`：健康检查、查询检查结果、生成摘要三个接口。
- `test_service.py`：使用本机随机端口的实际 HTTP 测试，不加载 Django，不读取生产配置。
- `knowledge/`：HTTP 参数、测试接口业务契约、验收方法三张知识卡。
- 正常组：E2E-A、alpha、healthy，摘要 `E2E-A | alpha | healthy | 12 ms`。
- 降级组：E2E-B、beta、degraded，摘要 `E2E-B | beta | degraded | 850 ms`。

## 本地运行

在仓库根目录执行：

```sh
python3 -m unittest discover -s scripts/harness_real_node_fixture -v
python3 scripts/harness_real_node_fixture/service.py --port 8769
```

本地入口只监听 `127.0.0.1`。它不能直接供云端 Engine 调用，不应通过关闭网络限制或临时公开隧道来冒充云端部署。

查询示例：

```sh
curl 'http://127.0.0.1:8769/v1/checks?check_id=E2E-A&service=alpha&scenario=healthy'
```

再把本次响应中的 check_id、service、status、latency_ms 和 request_id 分别放入摘要请求的 check_id、service、status、latency_ms、source_request_id。请求编号不得复制旧样例，完整字段见业务知识卡。

服务返回 `received` 和请求编号，并只把校验通过的合成字段写入标准输出。不记录 Cookie、Authorization、原始请求体或任意请求地址。此关联编号用于交叉核对，不是认证或防伪凭证。

## 云端部署边界

当前代码没有挂入 BKFlow 路由，也没有修改 `app_desc.yaml`、流水线或现有进程。本交付只包含本地准备，不会自动创建云端应用、模块或网关资源。

如需云端验证，应先确认独立测试模块和构建流水线，再将测试模块作为明确的可选交付。不改动既有模块的启动命令、数据库、增强服务、路由和现有环境变量；不能临时把接口塞进正在运行的服务。

独立模块的运行目标是本目录 `service:application`，使用平台生产 WSGI 进程管理器。现有项目已锁定 gunicorn 23.0.0，可沿用版本，但本包目前不包含云端部署描述或已构建镜像。最小模块不需要 MySQL、Redis、RabbitMQ 或应用密钥。

部署必须提供受控的内部访问地址、速率和请求大小限制，保持与其他模块的网络和凭证隔离。脚本自身没有认证，不可无保护公开到互联网。若走 APIGW，新建独立测试路径及 backend，保留既有资源认证策略；不得关闭既有接口鉴权。任何需要新增认证或网络授权的步骤应单独确认具体范围。

## 云端验收顺序

1. 测试服务上线，取得实际地址，验证 Engine 能访问；将地址录入测试配置，不让模型猜测。
2. 更新业务知识卡的部署状态并复验召回。BKAIDev 的知识库绑定与 BKFlow Knowledge Router 的空间绑定分开核验。
3. 保留原 Agent 对照配置；新的测试配置使用待验证模型、这三张知识卡和 Harness MCP。系统约束保留空间、凭证和执行边界，用户只给一句业务需求。
4. 让 Agent 选择实时插件 Schema，生成“查询检查结果、生成摘要、展示摘要”的草稿，核对真实参数绑定；不手工替模型写草稿后声称自动生成。
5. 在合法真实执行授权下先单步再全局调试。正常、降级两组必须让服务收到不同输入和各自本次的请求编号；全局真实调试被权限或审批拦截时如实停止。
6. 保留流程和调试记录，报告知识命中、结构校验、真实节点执行、变量传递和全局调试的各自结果。

## 已发现的产品契约问题

变量赋值插件 `value_assign v1.0.0` 的输入元数据描述为 object，而执行代码按列表遍历。首轮不使用该节点；该问题应修复 Schema 并回归真实执行，不能用知识卡教模型绕过校验。

消息展示 `bk_display v1.0` 的实现为空节点，仅展示输入，不负责数据转换或发通知。因此本轮真实执行证据以两个 HTTP 节点的请求和响应为主。
