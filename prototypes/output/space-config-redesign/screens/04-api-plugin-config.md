# API 插件 · 结构化配置 + 实时预览（api_plugin_config 复合控件）

[[ 空间配置 > API 与插件集成 > API 插件 ]]

::: card
#### 用途
把统一 API 网关按 api_key 结构化接入为可视化插件；每个 api_key 一套接入信息。

#### 影响
影响流程编辑中「API 插件」可选的接口与分类；改动可能影响已使用该接入的流程，请谨慎。

[查看文档](#)
:::

::: card
#### 通用设置 · common（对所有 api_key 生效）

空字段过滤 · exclude_none_fields
请求前剔除值为空的字段
((已开启)){success}

参数类型转换 · enable_api_parameter_conversion
对 POST 参数做 JSON 类型还原（字符串 → 数字/布尔/数组）
((已关闭))
:::

<!-- ❶ common 是跨全部 api_key 的通用开关，独立成区，不隶属某个 api_key。 -->

::: card
#### api_key: bkci

展示名称
[蓝盾统一 API____________]

Meta 接口 · apigw URL（必填，如 apigw.example.com/api/bkci/meta）
[必填，apigw meta 接口地址___]{type:url}

分类接口 · apigw URL（可选，如 apigw.example.com/api/bkci/categories）
[可选，apigw 分类接口地址___]{type:url}

请求头（可选）

| Key | Value | |
|-----|-------|-|
| X-Bkapi-Source | bkflow | [删除]{danger} |

::: row
[+ 添加请求头]{secondary}  [测试该 api_key]*
:::
:::

<!-- ❷ URL 控件即时校验 apigw 域名格式，非法标红。 -->
<!-- ❸ 每个 api_key 各带「测试」按钮，按 api_key 粒度验证（后端 verify 即按单个 api_key）。 -->

::: row
[+ 新增 api_key]{secondary}
:::

::: card
#### 验证 · 实时预览（当前测试：bkci）

状态：((成功)){success}

> **成功态**：拉取 meta / 分类成功 → 回显「接口 42 个、分类 8 个」+ 前 3 条样例
> **失败态**：((失败)){error} + 状态码 + 报错片段（如 502 Bad Gateway / 凭证无权限）；警告不阻断保存

| 接口 | Method | Path |
|------|--------|------|
| 创建流水线 | POST | /pipelines |
| 启动构建 | POST | /builds/start |
| 查询构建状态 | GET | /builds/{id} |

:::

<!-- ❹ 验证用「表单当前填的值」，未保存也能测；鉴权凭证默认取空间默认凭证（复用 UniformAPIClient meta/分类拉取）；预览区回显被测 api_key 的结果。 -->

::: row {right}
[高级（JSON 源码）]{secondary} [取消] [保存]*
:::
