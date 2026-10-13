# BKFlow HTTP 节点配置与输出绑定

适用范围：调用方明确指定的 BKFlow 隔离测试空间。内容版本 2026-10-12 v1。HTTP 节点字段依据当前代码核对；创建流程时仍须实时查询插件 Schema，不能把这张卡当作权限或执行授权。

## 选择真实节点

HTTP 请求使用 component 插件 bk_http_request，当前查询到版本 v1.0。一个 HTTP 节点实际发出一次网络请求；多个业务接口可用多个 HTTP 节点串联，不必为每个测试接口新增插件或 MCP 工具。

消息展示 bk_display v1.0 只是展示文本的空节点，不负责计算、JSON 提取或发送通知。它可以做最后的展示，不能作为真实外部调用的唯一证据。

变量赋值 value_assign v1.0.0 的公开 Schema 当前将 bk_assignment_list 描述为 object，但执行代码按赋值项列表处理。该契约不一致修复并验证前，不要猜测输入结构、强制绕过 Schema，或宣称该节点已可用。首轮用两个 HTTP 请求节点完成结果处理和传递。

## HTTP 请求参数

bk_http_request_method 是 GET 或 POST 等方法字符串。bk_http_request_url 是云端 Engine 可访问的完整地址；本机 127.0.0.1 不是云端测试地址。

bk_http_request_header 是数组，例如 [{"name":"Content-Type","value":"application/json"}]，不是普通字典。没有额外头时传 []。不要将令牌、Cookie、应用密钥写进流程、知识库或提示词。

bk_http_request_body 必须是字符串。GET 可传空字符串；POST JSON 先构造合法 JSON 字符串，数字保持数字，不能把整个对象的 Python 字符串表示当成 JSON。

bk_http_timeout 是整数，本轮使用 10 秒。bk_http_success_exp 是成功判断表达式，本测试接口可用 resp.ok == True。非 2xx 状态码或非 JSON 响应会失败，HTTP 200 也不自动代表业务成功。

输出字段 data 是整个响应 JSON 对象，status_code 是 HTTP 状态码。不要虚构 body、response 或任意自定义输出字段。

## 输出传到下一节点

a2flow v2 的变量 key 用 `${变量名}`。把查询节点 query_check 的 data 绑定为流程变量，可用变量声明：

```json
{"key":"${check_result}","name":"检查结果","source_type":"component_outputs","custom_type":"","source_info":{"query_check":["data"]},"show_type":"hide","value":{}}
```

source_info 的键是本次流程定义中的真实节点 ID，值是输出字段数组。下游通过该变量引用上游结果，不能把上次运行结果或知识卡示例值写死。嵌套字段可写成 `${check_result['check_id']}` 等表达式，必须通过当前校验与真实调试确认渲染结果。

对第二个 HTTP 节点，要核对真正收到的请求体：check_id、service、status、latency_ms、source_request_id 都来自本次第一节点输出；latency_ms 保持 JSON 数字。仅看到画布上的 `${...}` 或节点绿色，不代表参数传递成功。
