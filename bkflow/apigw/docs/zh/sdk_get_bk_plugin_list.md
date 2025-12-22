### 资源描述

获取第三方插件列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

| 字段           | 类型     | 必选 | 描述     |
|--------------|--------|----|--------|
| space_id     | int    | 否  | 空间ID   |
| tag          | int    | 否  | 插件分类id |
| manager      | string | 否  | 管理员    |
| search_term  | string | 否  | 搜索关键字  |

### 请求参数示例

```
GET /sdk/bk_plugin/?tag=4&space_id=213
```

### 返回结果示例

```json
{
     "result": true,
     "data": {
          "count": 9,
          "plugins": [
               {
                    "code": "test",
                    "name": "示例插件",
                    "tag": 4,
                    "logo_url": "https://example/bk_plugin_app_default.png",
                    "created_time": "2025-04-13 16:53:09 +0800",
                    "updated_time": "2025-05-14 15:48:46 +0800",
                    "introduction": "",
                    "managers": [
                         "xxx"
                    ],
                    "extra_info": {}
               }
          ]
     },
     "code": 0
}
```

### 返回结果参数说明

| 字段        | 类型       | 描述                    |
|-----------|----------|-----------------------|
| result    | bool     | 返回结果，true为成功，false为失败 |
| code      | int      | 返回码，0表示成功，其他值表示失败     |
| message   | string   | 错误信息                  |
| data      | list     | 返回数据，插件列表             |

#### data[plugins] 字段说明

| 字段           | 类型      | 描述        |
|--------------|---------|-----------|
| code         | string  | 插件代码      |
| name         | string  | 插件名称      |
| tag          | int     | 插件隶属分类    |
| logo_url     | string  | 插件图片url   |
| created_time | string  | 插件创建时间    |
| updated_time | string  | 插件更新时间    |
| introduction | string  | 插件简介      |
| managers     | list    | 插件管理员列表   |
| extra_info   | dict    | 额外信息      |


