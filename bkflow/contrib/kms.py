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

"""
KMS 敏感变量解密模块

根据蓝鲸 PaaS 平台 KMS 规范，从 /etc/secrets 读取加密信封和私钥，
解密后将敏感变量写回进程环境变量。

使用方式：
    from bkflow.contrib.kms import decrypt_kms_secrets

    # 在应用入口处调用
    decrypt_kms_secrets()
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def decrypt_kms_secrets():
    """
    解密 KMS 加密的敏感环境变量

    平台开启 KMS 后，容器内会提供：
    - /etc/secrets/envelope (加密后的敏感配置)
    - /etc/secrets/private-key (解密用的私钥)

    解密后的变量会写回 os.environ，业务代码可以正常读取环境变量。

    注意：调用前应确保 BKPAAS_KMS_ENABLED=true
    """
    logger.info("Starting to decrypt KMS secrets...")

    # 导入 bk-kms-sdk
    from bk_kms import decrypt

    # 读取信封和私钥
    secrets_root = Path("/etc/secrets")
    envelope_file = secrets_root / "envelope"
    private_key_file = secrets_root / "private-key"

    try:
        # 读取文件内容
        envelope = envelope_file.read_text(encoding="utf-8").strip()
        private_key = private_key_file.read_text(encoding="utf-8").strip()

        logger.info(f"Read envelope from {envelope_file}")
        logger.info(f"Read private key from {private_key_file}")

        # 解密信封
        plaintext = decrypt(envelope=envelope, private_key=private_key)

        # 解析 JSON
        config = json.loads(plaintext)

        # 提取敏感变量（只使用 env 字段）
        env_vars = config.get("env", {})

        if not env_vars:
            logger.warning("No environment variables found in decrypted config")
            return

        # 写回环境变量
        os.environ.update(env_vars)

        # 记录成功解密的变量名（不记录值）
        var_names = list(env_vars.keys())
        logger.info(f"Successfully decrypted and loaded {len(var_names)} environment variables: {', '.join(var_names)}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse decrypted config as JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to decrypt KMS secrets: {e}")
        raise
