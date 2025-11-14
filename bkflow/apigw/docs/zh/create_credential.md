### 资源描述

创建凭证

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 接口参数

| 字段      | 类型     | 必选 | 描述                    |
|---------|--------|----|-----------------------|
| name    | string | 是  | 凭证名称，最大长度32字符          |
| desc    | string | 否  | 凭证描述，最大长度32字符          |
| type    | string | 是  | 凭证类型，当前支持：BK_APP（蓝鲸应用凭证） |
| content | json   | 是  | 凭证内容，根据凭证类型不同而不同          |

### type 说明

当前支持的凭证类型：

| 凭证类型  | 说明        |
|-------|-----------|
| BK_APP | 蓝鲸应用凭证    |

### content 说明

#### 当 type 为 BK_APP 时：

content 需要包含以下字段：

```json
{
    "bk_app_code": "应用ID",
    "bk_app_secret": "应用密钥"
}
```

| 字段            | 类型     | 必选 | 描述                    |
|---------------|--------|----|-----------------------|
| bk_app_code   | string | 是  | 蓝鲸应用ID                |
| bk_app_secret | string | 是  | 蓝鲸应用密钥，不能全为 '*' 字符    |

### 请求参数示例

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "bk_username or bk_token": "xxxx",
    "name": "测试凭证",
    "desc": "这是一个测试凭证",
    "type": "BK_APP",
    "content": {
        "bk_app_code": "test_app",
        "bk_app_secret": "test_secret"
    }
}
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "id": 1,
        "space_id": 1,
        "desc": "这是一个测试凭证",
        "type": "BK_APP",
        "content": {
            "bk_app_code": "test_app",
            "bk_app_secret": "*********"
        }
    },
    "code": 0,
    "message": ""
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data

| 字段       | 类型     | 描述                    |
|----------|--------|-----------------------|
| id       | int    | 凭证ID                  |
| space_id | int    | 空间ID                  |
| desc     | string | 凭证描述                  |
| type     | string | 凭证类型                  |
| content  | dict   | 凭证内容（敏感信息会被脱敏显示）       |

### 注意事项

1. 凭证名称在同一个空间内必须唯一
2. 凭证内容中的敏感信息（如 bk_app_secret）在返回时会被脱敏处理，显示为 `*********`
3. 凭证类型目前仅支持 `BK_APP`，后续会支持更多类型
4. 创建凭证需要具有对应空间的权限


