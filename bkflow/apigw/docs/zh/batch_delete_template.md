### 资源描述

批量删除模板

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

#### 路径参数

| 字段       | 类型 | 必选 | 描述   |
|----------| --- | --- |------|
| space_id | int | 是 | 空间ID |

#### 接口参数

| 字段 | 类型   | 必选 | 描述     |
| --- |------| --- |--------|
| template_ids | list | 是 | 模板ID列表 |


### 返回结果示例

```json
{
    "result": true,
    "data": {},
    "code": 0,
    "trace_id": "3b9bc1fa61cb498ea6fb74fc0f444159"
}
```

### 删除失败示例
```json
{
    "result": false,
    "data": {
        "root_template_info": {
            "1": [
                {
                    "root_template_id": "20",
                    "root_template_name": "测试流程"
                }
            ]
        },
        "decision_info": {
            "1": [
                {
                    "id": 5,
                    "name": "决策表A"
                }
            ]
        }
    },
    "code": 400,
    "message": "模板被引用，无法删除",
    "trace_id": "00-36749a2619963cadf480a1597d98a6ee-33ff46feb2870f06-01"
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                |
| ------- | ------ |-------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败 |
| message | string | 错误信息              |
| data    | dict  | 返回数据（删除失败时返回引用信息，结构见下方） |

#### data 失败结构说明

删除失败时，`data` 可能包含以下字段：

| 字段      | 类型     | 描述                |
| ------- | ------ |-------------------|
| root_template_info | dict  | 子流程被父流程引用信息，key 为子流程模板ID，value 为引用它的父流程列表（含 `root_template_id` 与 `root_template_name`） |
| decision_info | dict  | 模板关联的决策表信息，key 为模板ID，value 为关联决策表列表（含 `id` 与 `name`）；仅当存在关联决策表时返回 |
