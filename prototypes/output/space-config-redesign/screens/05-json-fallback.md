# 复合项 · JSON 源码兜底（高级模式）

[[ 空间配置 > API 与插件集成 > API 插件 ]]

::: row
[结构化] [JSON 源码]*
:::

<!-- ❶ 复合控件右上角切换「结构化 ↔ JSON 源码」，双向同步、校验后互转，为熟练用户留逃生通道。 -->

::: card
#### JSON 源码（Monaco 编辑器占位）

```json
{
  "bkci": {
    "display_name": "蓝盾统一 API",
    "meta_apis": "https://apigw.example.com/api/bkci/meta",
    "api_categories": "https://apigw.example.com/api/bkci/categories",
    "headers": { "X-Bkapi-Source": "bkflow" },
    "common": true
  }
}
```

> **无法结构化解析的旧值**（如旧版 V1 顶层 meta_apis）自动落到此 JSON 模式，不卡死用户；能解析的照常回结构化。
:::

<!-- ❷ 切回「结构化」前先校验 JSON；非法则标红并阻止切换，提示错误行。 -->

::: card
#### 验证

::: row
[测试连接]{secondary}
:::

状态：((待测试))

> 与结构化模式共用同一 verify 接口，测的是当前源码里的值。
:::

::: row {right}
[取消] [保存]*
:::
