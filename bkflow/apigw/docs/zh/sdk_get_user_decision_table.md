### 资源描述

获取用户决策表插件列表（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 接口参数

| 字段         | 类型     | 必选 | 描述       |
|------------|--------|----|----------|
| space_id   | int    | 否  | 空间ID     |
| template_id | int    | 否  | 模板ID     |

### 请求参数示例

```
GET /sdk/decision_table/user/?space_id=1&template_id=1
```

### 返回结果示例

```json
{
    "result": true,
    "data": [
        {
            "id": 1,
            "space_id": 1,
            "template_id": 1,
            "name": "决策表1",
            "desc": "决策表描述",
            "data": {
                "inputs": [],
                "outputs": [],
                "rules": []
            },
            "create_at": "2024-01-01T00:00:00Z",
            "update_at": "2024-01-01T00:00:00Z"
        }
    ],
    "code": 0
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | list   | 返回数据，决策表列表            |

#### data[item] 字段说明

| 字段         | 类型     | 描述       |
|------------|--------|----------|
| id         | int    | 决策表ID    |
| space_id   | int    | 空间ID     |
| template_id | int    | 模板ID     |
| name       | string | 决策表名称   |
| desc       | string | 决策表描述   |
| data       | dict   | 决策表数据   |
| create_at  | string | 创建时间    |
| update_at  | string | 更新时间    |


