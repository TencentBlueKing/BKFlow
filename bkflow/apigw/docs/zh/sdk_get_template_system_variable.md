### 资源描述

获取系统变量（SDK接口）

### 输入通用参数说明

| 参数名称          | 参数类型   | 必须 | 参数说明                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | 是  | 应用ID(app id)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取     |
| bk_app_secret | string | 是  | 安全秘钥(app secret)，可以通过 蓝鲸开发者中心 -> 应用基本设置 -> 基本信息 -> 鉴权信息 获取 |

### 权限说明

该接口使用默认权限，**不需要 HTTP_BKFLOW_TOKEN**。

### 接口参数

无

### 请求参数示例

```
GET /sdk/template/variable/system_variable/
```

### 返回结果示例

```json
{
    "result": true,
    "data": {
        "${_system.task_name}": {
            "key": "${_system.task_name}",
            "name": "任务名称",
            "index": -1,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.task_id}": {
            "key": "${_system.task_id}",
            "index": -2,
            "name": "任务ID",
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.task_start_time}": {
            "key": "${_system.task_start_time}",
            "name": "任务开始时间",
            "index": -3,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        },
        "${_system.operator}": {
            "key": "${_system.operator}",
            "name": "任务的执行人（点击开始执行的人员）",
            "index": -4,
            "desc": "",
            "show_type": "hide",
            "source_type": "system",
            "source_tag": "",
            "source_info": {},
            "custom_type": "",
            "value": "",
            "hook": false,
            "validation": ""
        }
    },
    "code": "0",
    "message": ""
}
```

### 返回结果参数说明

| 字段      | 类型     | 描述                    |
|---------|--------|-----------------------|
| result  | bool   | 返回结果，true为成功，false为失败 |
| code    | string | 返回码，0表示成功，其他值表示失败     |
| message | string | 错误信息                  |
| data    | dict   | 返回数据，系统变量字典            |

#### data[item] 字段说明

| 字段                         | 类型      | 描述         |
|----------------------------|---------|------------|
| ${_system.task_name}       | string  | 系统变量任务名称   |
| ${_system.task_id}         | string  | 系统变量任务id   |
| ${_system.task_start_time} | string  | 系统变量任务开始事件 |
| ${_system.operator}        | string  | 系统变量任务执行人  |



#### ${_system.task_name}[messages] 字段说明

| 字段          | 类型      | 描述                     |
|-------------|---------|------------------------|
| key         | string  | 变量键名                   |
| name        | string  | 变量名称                   |
| desc        | string  | 变量描述                   |
| desc        | string  | 变量描述                   |
| index       | integer | 展示在前端全局变量的顺序，越小越靠前     |
| show_type   | string  | 显示类型：hide(隐藏)/show(显示) |
| source_type | string  | 来源类型：system(系统变量)      |
| source_tag  | string  | 来源标签                   |
| source_info | object  | 来源信息                   |
| custom_type | string  | 自定义类型                  |
| value       | string  | 变量值                    |
| hook        | bool    | 是否启用hook               |
| validation  | string  | 验证规则                   |
