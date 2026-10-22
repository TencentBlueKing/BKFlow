# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.
"""


import os

from blueapps.core.wsgi import get_wsgi_application

"""
WSGI config for project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# ========== 本地测试：模拟 KMS 解密 ==========
if os.environ.get('BKPAAS_KMS_ENABLED', '') == 'true':
    # 生产环境：使用真实的 KMS 解密
    from bkflow.contrib.kms import decrypt_kms_secrets
    decrypt_kms_secrets()
elif os.environ.get('LOCAL_KMS_TEST', '') == 'true':
    # 本地测试：使用模拟解密
    print("\n🧪 [本地测试模式] 使用模拟 KMS 解密\n")
    from bkflow.contrib.kms_mock import mock_decrypt_kms_secrets
    mock_decrypt_kms_secrets()
# ==============================================

application = get_wsgi_application()

# ========== 验证解密结果 ==========
if os.environ.get('LOCAL_KMS_TEST', '') == 'true':
    from bkflow.contrib.kms_mock import verify_decryption
    verify_decryption()
# =================================
