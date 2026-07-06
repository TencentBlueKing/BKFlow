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
#### api_key: bkci  ((common)){primary}

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

[+ 添加请求头]{secondary}  [+ 新增 api_key]{secondary}
:::

<!-- ❶ 多 api_key 分块编辑；((common)) 徽标表示是否作为通用接入。 -->
<!-- ❷ URL 控件即时校验 apigw 域名格式，非法标红。 -->

::: card
#### 验证 · 实时预览

::: row
[测试连接]*
:::

状态：((成功)){success}

> **成功态**：拉取 meta / 分类成功 → 回显「接口 42 个、分类 8 个」+ 前 3 条样例
> **失败态**：((失败)){error} + 状态码 + 报错片段（如 502 Bad Gateway / 凭证无权限）；警告不阻断保存

| 接口 | Method | Path |
|------|--------|------|
| 创建流水线 | POST | /pipelines |
| 启动构建 | POST | /builds/start |
| 查询构建状态 | GET | /builds/{id} |

:::

<!-- ❸ 验证用「表单当前填的值」，未保存也能测；鉴权凭证默认取空间默认凭证（复用 UniformAPIClient meta/分类拉取）。 -->

::: row {right}
[高级（JSON 源码）]{secondary} [取消] [保存]*
:::
