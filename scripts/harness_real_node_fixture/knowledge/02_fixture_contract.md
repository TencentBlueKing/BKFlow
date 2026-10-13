# 隔离测试空间的接口检查与摘要生成示例

适用范围：调用方明确指定的隔离测试空间中的合成数据联调。内容版本 2026-10-12 v1。测试接口的本地实现已完成；本包不提供云端部署地址。部署完成前只能准备或校验流程，不可把下面路径拼接到猜测的域名后运行。fixture_base_url 必须由测试部署提供，不来自模型猜测或任意外部 URL。

## 业务需求

帮我检查 alpha 测试服务，把检查结果交给摘要接口，最后展示摘要。检查编号 E2E-A，正常场景。

推荐三个节点：查询检查结果（真实 HTTP GET）、生成摘要（真实 HTTP POST）、展示摘要（消息展示）。前两个节点是真实网络调用，接口返回的是合成业务数据，不是生产服务状态，也不是 Harness mock 输出。

## 查询接口

GET {fixture_base_url}/v1/checks?check_id=E2E-A&service=alpha&scenario=healthy。

check_id 为 1 到 64 位字母、数字、下划线或短横线。service 只能为 alpha 或 beta。scenario 只能为 healthy 或 degraded。不能传生产服务、目标 URL、令牌、任意字段或重复参数。

健康场景响应格式：{"ok":true,"synthetic":true,"request_id":"本次服务器生成的 UUID","check_id":"E2E-A","service":"alpha","status":"healthy","latency_ms":12,"received":{"check_id":"E2E-A","service":"alpha","scenario":"healthy"}}。

降级场景仍返回 HTTP 200、ok=true，但 status 为 degraded，latency_ms 为 850。它表示成功查询到降级状态，不是 HTTP 调用失败。request_id 每次生成，不能复制示例或上次运行的值。

## 摘要接口

POST {fixture_base_url}/v1/reports，Content-Type: application/json。请求体为 {"check_id":"来自查询结果","service":"来自查询结果","status":"来自查询结果","latency_ms":12,"source_request_id":"来自查询结果的 request_id"}。其中 12 只是类型示例，实际取上游 latency_ms；五个字段都必须取本次查询结果。

响应包括 ok=true、synthetic=true、独立 request_id、source_request_id、received 和 summary。正常样例的 summary 应为 E2E-A | alpha | healthy | 12 ms；换成 E2E-B、beta、degraded 后应为 E2E-B | beta | degraded | 850 ms。received 是服务实际收到并校验通过的字段，用来核对参数传递，不是模型推断。

该 POST 只生成摘要回包和合成数据请求日志，不创建工单、不发通知、不调用别的服务，不写业务数据库。未知字段、漏字段、错误类型返回 400；正文超过 4096 字节返回 413；非 JSON 类型返回 415。

## 流程输出

将摘要节点 build_report 的 data 绑定为 `${report_result}`。展示输入使用 `${report_result['summary']}`。需要用户看到的流程输出也从 report_result 取值，而不是重新根据初始参数拼一个看起来正确的答案。

接口地址、插件实时 Schema、实际执行授权是三个不同前提。知识卡不提供凭证，不放行真实执行，也不替代空间和环境的权限检查。
