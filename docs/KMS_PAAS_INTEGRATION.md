# BKFlow KMS 集成文档

## 概述

根据蓝鲸 PaaS 平台 KMS 规范，本项目已集成 KMS 敏感变量解密功能。

## 一、平台提供什么

开启 KMS 后，每个进程都会获得：

| 内容 | 说明 |
|------|------|
| `BKPAAS_KMS_ENABLED=true` | 开关：敏感配置要从文件里读 |
| `/etc/secrets/envelope` | 加密后的敏感配置（信封） |
| `/etc/secrets/private-key` | 解开信封用的钥匙 |

交给 KMS 的变量：
- 页面上勾选「敏感」的变量
- 增强服务的密码类字段
- 内置的 `BKPAAS_APP_SECRET`

## 二、什么是信封

信封就是 `/etc/secrets/envelope` 文件，是一长串 Base64 编码的字符串。

用 `/etc/secrets/private-key` 解密后，得到的 JSON 结构：

```json
{
  "schema_version": 1,
  "config_version_id": "...",
  "module_environment_id": "...",
  "env": {
    "BKPAAS_APP_SECRET": "xxxx",
    "DATABASE_PASSWORD": "xxxx",
    "REDIS_PASSWORD": "xxxx"
  }
}
```

**注意**：
- 只使用 `env` 字段，其他是平台字段
- 解密在容器内本地完成，不需要联网
- 一次部署对应一个信封，改了变量要重新部署

## 三、安装依赖

### requirements.txt

```txt
bk-kms-sdk[gm]==1.0.0  # gm 为国密依赖
```

### 安装命令

```bash
pip install 'bk-kms-sdk[gm]'
```

**要求**：Python >=3.11, <3.15

## 四、使用方法

### 4.1 在应用入口调用

在读取配置之前调用解密函数：

```python
from bkflow.contrib.kms import decrypt_kms_secrets

# 解密 KMS 敏感变量
decrypt_kms_secrets()

# 之后正常读取环境变量
import os
db_password = os.getenv('DATABASE_PASSWORD')
```

### 4.2 各个入口都要解密

每条启动命令是独立进程，各自解密一次：

#### Web 入口 (wsgi.py)

```python
import os
from django.core.wsgi import get_wsgi_application
from bkflow.contrib.kms import decrypt_kms_secrets

# 在初始化 Django 之前解密
decrypt_kms_secrets()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
application = get_wsgi_application()
```

#### Celery Worker 入口

```python
from celery import Celery
from bkflow.contrib.kms import decrypt_kms_secrets

# 在创建 Celery 应用之前解密
decrypt_kms_secrets()

app = Celery('bkflow')
app.config_from_object('django.conf:settings', namespace='CELERY')
```

#### 自定义脚本

```python
from bkflow.contrib.kms import decrypt_kms_secrets
import sys

try:
    decrypt_kms_secrets()
except Exception as e:
    print(f"Failed to decrypt KMS: {e}")
    sys.exit(1)

# 业务逻辑
```

#### manage.py

```python
import os
import sys
from bkflow.contrib.kms import decrypt_kms_secrets

# 在执行任何命令之前解密
decrypt_kms_secrets()

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    # ...
```

### 4.3 推荐方式：在 bkflow/__init__.py 中自动加载

```python
# bkflow/__init__.py
from bkflow.contrib.kms import decrypt_kms_secrets

# 模块导入时自动解密
decrypt_kms_secrets()
```

这样所有导入 bkflow 的入口都会自动解密。

## 五、验证

### 5.1 检查环境

进入容器执行：

```bash
# 检查 KMS 开关
env | grep BKPAAS_KMS_ENABLED

# 检查文件
ls /etc/secrets

# 检查解密后的变量
env | grep -E 'DATABASE_PASSWORD|REDIS_PASSWORD|BKPAAS_APP_SECRET'
```

### 5.2 常见现象

| 现象 | 原因 |
|------|------|
| 没有 `BKPAAS_KMS_ENABLED` 和 `/etc/secrets` | 平台或应用未开启，或开启后没重新部署 |
| 有 `/etc/secrets`，启动报错退出 | 缺少解密依赖，或自定义入口没调用加载代码 |
| 敏感变量仍是明文 | 变量写在 `app_desc.yaml` 里，没在页面上勾选「敏感」 |
| 值以 `bkpaas_enc$` 开头 | 平台未开启 SaaS KMS，走的是旧加密 |

## 六、开启与部署

### 6.1 开启 KMS

1. 平台运维开启 `PAAS_SAAS_KMS_ENABLED`
2. 为应用开启特性「加密运行环境敏感变量」

### 6.2 部署注意事项

**必须完整部署才生效**：

- ✅ 完整部署：会生成新信封
- ❌ 重启进程：用的是旧信封
- ❌ 静默发布：跳过构建，不生成新信封

**改了敏感变量后，必须重新部署**。

### 6.3 不要做的事

- ❌ 不要自己定义 `BKPAAS_KMS_ENABLED`
- ❌ 不要占用 `/etc/secrets` 路径
- ❌ 不要占用 `kms-secret` 卷名
- ❌ 不要将敏感变量写在 `app_desc.yaml` 的 `env_variables` 中

## 七、S-Mart 应用特别注意

1. **敏感变量配在页面上**，不要写进 `app_desc.yaml`
   - 描述文件里的 `env_variables` 没有「敏感」选项，永远是明文

2. **安装包带上依赖**
   - `requirements.txt` 加 `bk-kms-sdk[gm]`
   - Python 版本 >=3.11, <3.15
   - 自带运行环境的包要在打包前装好

3. **检查所有命令**
   - 检查 `app_desc.yaml` 里的每条命令（`processes`、`pre_release_hook`）
   - 自定义脚本都要调用 `decrypt_kms_secrets()`

## 八、API 参考

### decrypt_kms_secrets()

```python
from bkflow.contrib.kms import decrypt_kms_secrets

decrypt_kms_secrets()
```

**功能**：
- 检查 `BKPAAS_KMS_ENABLED` 是否为 `true`
- 读取 `/etc/secrets/envelope` 和 `/etc/secrets/private-key`
- 解密信封，提取 `env` 字段
- 将敏感变量写回 `os.environ`

**异常**：
- `ImportError`: 未安装 `bk-kms-sdk`
- `FileNotFoundError`: 找不到信封或私钥文件
- `json.JSONDecodeError`: 解密后的内容不是有效 JSON
- 其他解密相关异常

**日志**：
- 只记录变量名，不记录变量值
- 成功时记录解密的变量数量和名称

### is_kms_enabled()

```python
from bkflow.contrib.kms import is_kms_enabled

if is_kms_enabled():
    print("KMS is enabled")
```

**返回**：`True` 如果 `BKPAAS_KMS_ENABLED=true`

## 九、安全注意事项

### 能防

- ✅ 部署记录中不再出现明文
- ✅ 进程定义中不再出现明文
- ✅ `kubectl describe` 看不到明文
- ✅ 平台日志中不再出现明文

### 不能防

- ❌ 能进入容器的人（信封、钥匙和明文都在容器里）
- ❌ 应用自己把配置打进日志或接口返回

**容器访问权限仍需单独管控**。

## 十、故障排查

### 问题 1: ModuleNotFoundError: No module named 'bk_kms'

**解决**：
```bash
pip install 'bk-kms-sdk[gm]'
```

### 问题 2: FileNotFoundError: /etc/secrets/envelope

**原因**：
- KMS 未开启
- 开启后没有重新部署

**解决**：完整部署应用

### 问题 3: 启动报错退出

**原因**：自定义入口没有调用 `decrypt_kms_secrets()`

**解决**：在所有启动脚本中添加解密调用

### 问题 4: 变量仍是明文

**原因**：变量没有在页面上勾选「敏感」

**解决**：在环境变量配置页面勾选变量为「敏感」，然后重新部署

## 十一、文件清单

```
BKFlow/
├── bkflow/
│   └── contrib/
│       ├── kms.py              # KMS 解密模块（新增）
│       └── kms_example.py      # 使用示例（新增）
├── requirements.txt            # 添加 bk-kms-sdk[gm]（已修改）
└── docs/
    └── KMS_PAAS_INTEGRATION.md # 本文档（新增）
```

## 十二、原理（选读）

### 加密流程

1. 开发者中心挑出敏感变量，从环境变量里拿掉
2. 获取 KMS 集群的加密公钥
3. 随机生成对称密钥，用它加密变量清单
4. 用公钥（RSA/SM2）加密对称密钥
5. 两者打包成信封，存入 KMS

### 同步流程

1. 在应用命名空间创建同步配置
2. 集群内的 External Secrets 组件从 KMS 取回信封和私钥
3. 生成该环境专属的 Secret
4. 以只读文件挂载到 `/etc/secrets`

### 启动流程

1. 容器等待文件就绪
2. 挂载 `/etc/secrets`
3. 启动进程
4. 应用调用 `decrypt_kms_secrets()` 解密
5. 变量写回进程环境

### 版本管理

- 每次部署对应一个配置版本
- 内容不变时复用
- 部署成功后回收不再使用的旧版本

---

**文档版本**: 1.0  
**更新时间**: 2024  
**适用范围**: 蓝鲸 PaaS 平台 KMS 功能
