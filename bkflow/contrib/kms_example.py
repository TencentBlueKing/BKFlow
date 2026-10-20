"""
KMS 集成示例

展示如何在不同的应用入口调用 KMS 解密
"""

# ============================================================
# 示例 1: 在 Django 入口（manage.py 或 wsgi.py）
# ============================================================

# wsgi.py
import os
from django.core.wsgi import get_wsgi_application

# 在初始化 Django 之前解密 KMS 密钥
from bkflow.contrib.kms import decrypt_kms_secrets
decrypt_kms_secrets()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
application = get_wsgi_application()


# ============================================================
# 示例 2: 在 Celery Worker 入口
# ============================================================

# celery.py 或 worker 启动脚本
from celery import Celery
from bkflow.contrib.kms import decrypt_kms_secrets

# 在创建 Celery 应用之前解密
decrypt_kms_secrets()

app = Celery('bkflow')
app.config_from_object('django.conf:settings', namespace='CELERY')


# ============================================================
# 示例 3: 在自定义管理脚本
# ============================================================

# scripts/custom_script.py
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 解密 KMS
from bkflow.contrib.kms import decrypt_kms_secrets
decrypt_kms_secrets()

# 现在可以读取敏感环境变量
db_password = os.getenv('DATABASE_PASSWORD')
api_secret = os.getenv('API_SECRET')


# ============================================================
# 示例 4: 在 local_settings.py 中使用
# ============================================================

# local_settings.py
from bkflow.contrib.kms import decrypt_kms_secrets, is_kms_enabled

# 解密 KMS（如果启用）
decrypt_kms_secrets()

# 之后正常读取环境变量
import os

if is_kms_enabled():
    # KMS 已启用，环境变量已被解密
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DATABASE_NAME'),
            'USER': os.getenv('DATABASE_USER'),
            'PASSWORD': os.getenv('DATABASE_PASSWORD'),  # 已解密
            'HOST': os.getenv('DATABASE_HOST'),
            'PORT': os.getenv('DATABASE_PORT'),
        }
    }


# ============================================================
# 示例 5: 条件调用（推荐）
# ============================================================

from bkflow.contrib.kms import decrypt_kms_secrets

# 解密会自动检查 BKPAAS_KMS_ENABLED，未启用时直接跳过
# 所以可以在所有入口都添加这行，不影响本地开发
decrypt_kms_secrets()


# ============================================================
# 示例 6: 带异常处理的调用
# ============================================================

from bkflow.contrib.kms import decrypt_kms_secrets
import sys

try:
    decrypt_kms_secrets()
except Exception as e:
    print(f"Failed to decrypt KMS secrets: {e}")
    sys.exit(1)


# ============================================================
# 示例 7: 在 __init__.py 中自动加载
# ============================================================

# bkflow/__init__.py
# 在模块导入时自动解密（推荐）
from bkflow.contrib.kms import decrypt_kms_secrets

try:
    decrypt_kms_secrets()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to load KMS secrets: {e}")
    # 根据需要决定是否抛出异常
    raise
