### 资源描述

获取获取插件服务App详情（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

| 字段            | 类型     | 必选 | 描述       |
|---------------|--------|----|----------|
| plugin_code   | string | 是  | 插件代码     |

### 请求参数示例

```
GET /sdk/plugin_service/app_detail/?plugin_code=example_plugin
```

### 返回结果示例

```json
{
     "result": true,
     "message": null,
     "data": {
          "url": "http://example.com/",
          "urls": [
               "http://example.com/",
               "http://example.com/"
          ],
          "name": "示例插件",
          "desc": "插件描述",
          "updated": "2025-06-12 14:34:52 +0800",
          "apigw_name": "xxx",
          "tag_info": {
               "id": 4,
               "name": "未分类",
               "code_name": "OTHER",
               "priority": 1
          }
     },
     "code": 0
}
```


### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data 字段说明

| 字段            | 类型      | 描述          |
|---------------|---------|-------------|
| url           | string  | 当前环境下的默认地址  |
| urls          | list    | 当前环境下所有访问地址 |
| name          | string  | 插件名称        |
| desc          | string  | 插件描述        |
| updated       | string  | 更新时间        |
| apigw_name    | string  | API 网关名称    |
| tag_info      | dict    | 插件基本信息      |


