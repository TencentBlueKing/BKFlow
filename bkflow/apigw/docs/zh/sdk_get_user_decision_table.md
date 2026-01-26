### 资源描述

获取用户决策表插件列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### HTTP Header 参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| HTTP_BKFLOW_TOKEN | string | 是  | 访问令牌，需要通过 `/space/{space_id}/apply_token/` 接口申请。该 token 用于验证用户对指定空间和模板的访问权限 |

### 接口参数

| 字段         | 类型     | 必选 | 描述       |
|------------|--------|----|----------|
| space_id   | int    | 否  | 空间ID     |
| template_id | int    | 否  | 模板ID     |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "space_id": 1,
    "template_id": 1
}
```

### 返回结果示例

```json
{
  "result": true,
  "data": {
    "count": 29,
    "next": "",
    "previous": null,
    "results": [
      {
        "id": 66,
        "create_at": "2025-06-23 17:07:48+0800",
        "update_at": "2025-06-23 17:07:48+0800",
        "creator": "v_jinhpeng",
        "updated_by": "v_jinhpeng",
        "is_deleted": false,
        "name": "新画布决策",
        "desc": "",
        "space_id": 1,
        "template_id": 1222,
        "scope_type": "",
        "scope_value": "",
        "data": {
          "inputs": [
            {
              "id": "fieldf90fc9ce",
              "desc": "",
              "from": "inputs",
              "name": "文本",
              "tips": "",
              "type": "string"
            }
          ],
          "outputs": [
            {
              "id": "fieldfc79a383",
              "desc": "",
              "from": "outputs",
              "name": "数字",
              "tips": "",
              "type": "int"
            }
          ],
          "records": [
            {
              "inputs": {
                "type": "common",
                "conditions": [
                  {
                    "right": {
                      "obj": {
                        "type": "string",
                        "value": "11"
                      },
                      "type": "value"
                    },
                    "compare": "equals"
                  }
                ]
              },
              "outputs": {
                "fieldfc79a383": 22
              }
            }
          ]
        },
        "table_type": "single",
        "extra_info": {}
      }
    ],
    "code": "0",
    "message": ""
  }
}
```

### 返回结果参数说明

| 字段       | 类型      | 描述                    |
|----------|---------|-----------------------|
| result   | bool    | 返回结果，true为成功，false为失败 |
| code     | string  | 返回码，0表示成功，其他值表示失败     |
| message  | string  | 错误信息                  |
| data     | dict    | 返回数据                  |

#### data[item] 字段说明

| 字段          | 类型     | 描述    |
|-------------|--------|-------|
| id          | int    | 决策表ID |
| space_id    | int    | 空间ID  |
| template_id | int    | 模板ID  |
| name        | string | 决策表名称 |
| desc        | string | 决策表描述 |
| data        | dict   | 决策表数据 |
| create_at   | string | 创建时间  |
| update_at   | string | 更新时间  |
| creator     | string | 创建人   |
| updated_by  | string | 更新人   |
| is_deleted  | bool   | 是否删除  |
| scope_type  | string | 作用域类型 |
| scope_value | string | 作用域值  |
