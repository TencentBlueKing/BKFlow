### 资源描述

通过 bk_app_code 权限校验创建任务

此接口用于绑定了 bk_app_code 的流程创建任务，请求方的 bk_app_code 需要与流程模板绑定的 bk_app_code 一致才能创建任务。

### 输入通用参数说明
| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |


#### 接口参数

| 字段          | 类型     | 必选 | 描述     |
|-------------|--------|----|--------|
| name        | string | 否  | 任务名    |
| creator     | string | 是  | 创建者    |
| description | string | 否  | 描述     |
| constants   | json   | 否  | 任务启动参数 |


路径参数:

| 字段      | 类型     | 必选 | 描述                                              |
|---------|--------|----|-------------------------------------------------|
| template_id | int | 是  | 模板 ID |


### 权限说明

- 模板必须绑定了 bk_app_code（创建模板时通过 bk_app_code 参数指定）
- 请求方的 bk_app_code 必须与模板绑定的 bk_app_code 一致

### 请求参数示例

```json
{
    "name": "任务名称",
    "creator": "创建者",
    "constants": {
        "${param1}": "value1"
    }
}
```

### 返回结果示例

```json
{
	"result": true,
	"data": {
		"id": 10,
		"space_id": 1,
		"scope_type": null,
		"scope_value": null,
		"instance_id": "6e15e7cf27ab3129878cdd9b95fff006",
		"template_id": 4,
		"name": "任务名称",
		"creator": "创建者",
		"create_time": "2023-04-23T21:10:06.826644+08:00",
		"executor": "",
		"start_time": null,
		"finish_time": null,
		"description": "",
		"is_started": false,
		"is_finished": false,
		"is_revoked": false,
		"is_deleted": false,
		"is_expired": false,
		"snapshot_id": 3,
		"execution_snapshot_id": 8,
		"tree_info_id": null,
		"extra_info": {}
	},
	"code": "0",
	"message": ""
}
```

### 错误返回示例

模板未绑定 bk_app_code:
```json
{
    "result": false,
    "message": "Template is not bindedto any bk_app_code. template_id=3"
}
```

bk_app_code 不匹配:
```json
{
    "result": false,
    "message": "The current application does not have permission to operate this template, app=other_app, template bindedapp=your_app"
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | int    | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据                  |

#### data[item]

| 字段                    | 类型     | 描述       |
|-----------------------|--------|----------|
| id                    | int    | 任务ID     |
| space_id              | int    | 空间ID     |
| scope_type            | string | 任务范围类型   |
| scope_value           | string | 任务范围值    |
| instance_id           | string | 实例ID     |
| template_id           | int    | 模板ID     |
| name                  | string | 任务名称     |
| creator               | string | 创建者      |
| create_time           | string | 创建时间     |
| executor              | string | 执行者      |
| start_time            | string | 开始时间     |
| finish_time           | string | 结束时间     |
| description           | string | 描述       |
| is_started            | bool   | 是否已开始    |
| is_finished           | bool   | 是否已结束    |
| is_revoked            | bool   | 是否已撤销    |
| is_deleted            | bool   | 是否已删除    |
| is_expired            | bool   | 是否已过期    |
| snapshot_id           | int    | 快照ID     |
| execution_snapshot_id | int    | 执行快照ID   |
| tree_info_id          | int    | 任务拓扑信息ID |
| extra_info            | dict   | 任务额外信息   |

