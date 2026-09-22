### Resource description

Grant API gateway permissions to other applications

### Common authentication parameters
| Parameter          | Type   | Required | Description                                                       |
|---------------|--------|----|------------------------------------------------------------|
| bk_app_code   | string | Yes  | Application ID (app ID), available in BlueKing Developer Center > Application settings > Basic information > Authentication information     |
| bk_app_secret | string | Yes  | Application secret (app secret), available in BlueKing Developer Center > Application settings > Basic information > Authentication information |


#### Endpoint parameters

| Field          | Type     | Required | Description              |
|-------------|--------|----|-----------------|
| apps        | list   | Yes  | List of app_codes to authorize |
| permissions | list   | Yes  | List of endpoint IDs to authorize     |


### Request example

```json
{
    "bk_app_code": "xxxx",
    "bk_app_secret": "xxxx",
    "apps": ["xxx"],
    "permissions": ["create_space"]
}
```

### Response example

```json
{
	"result": true,
	"data": "permission granted",
	"code": "0",
	"message": ""
}

```
### Response parameters

| Field      | Type     | Description                    |
|---------|--------|-----------------------|
| result  | bool   | Operation result: true for success, false for failure |
| code    | int    | Response code: 0 for success, any other value for failure     |
| message | string | Error message                  |
| data    | dict   | Response data                  |
