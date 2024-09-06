# 业务拓展

接入系统支持通过蓝鲸插件、API 插件和 Webhook 订阅进行业务拓展。

1. 蓝鲸插件开发：[开发文档](https://github.com/TencentBlueKing/bk-plugin-framework-python)
2. API 插件开发：[API 插件开发](./api_plugin.md)
3. Webhook 订阅：通过调用 [apply_webhook_configs api](../../bkflow/apigw/docs/zh/apply_webhook_configs.md)，可以对事件进行订阅。当对应的事件触发时，BKFlow 会自动进行回调，接入系统可以对回调请求进行自定义处理。
