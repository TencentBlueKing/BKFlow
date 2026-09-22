# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.

密码变量加解密工具，迁移自蓝鲸智云标准运维(gcloud.utils.crypto)
"""
import base64
import re
import typing

from bkcrypto import constants as crypto_constants
from bkcrypto.asymmetric.configs import KeyConfig as AsymmetricKeyConfig
from bkcrypto.contrib.django.selectors import AsymmetricCipherSelector
from django.conf import settings


def get_default_asymmetric_key_config(cipher_type: str) -> AsymmetricKeyConfig:
    """
    获取项目默认非对称加密配置
    :param cipher_type:
    :return:
    """
    if cipher_type == crypto_constants.AsymmetricCipherType.SM2.value:
        private_key_string: str = settings.SM2_PRIV_KEY
        public_key_string: str = settings.SM2_PUB_KEY
    elif cipher_type == crypto_constants.AsymmetricCipherType.RSA.value:
        private_key_string: str = settings.RSA_PRIV_KEY
        public_key_string: str = settings.RSA_PUB_KEY
    else:
        raise NotImplementedError(f"cipher_type -> {cipher_type}")

    return AsymmetricKeyConfig(
        private_key_string=private_key_string.strip("\n"), public_key_string=public_key_string.strip("\n")
    )


def _convert_hex_ciphertext_to_base64(ciphertext: str, using: str) -> str:
    """
    将 hex 编码的密文体转换为 base64 编码，并保留原算法前缀。

    前端 jsencrypt 的 RSAKey.encrypt() 返回的是 hex 串。本项目使用的 jsencrypt 2.3.0
    其 `lib/jsbn/base64.js` 为全局脚本、无 export，前端无法调用 hex2b64 做转换，
    因此前端上报的密文为 hex 编码；而后端 bkcrypto 默认使用 Base64Convertor 解码，
    遇到 hex 串会解密失败。这里做兜底转换。

    :param ciphertext: 带算法前缀的密文
    :param using: bkcrypto 中的实例名
    :return: 转换后的密文；若密文非 hex 形态或无法获取前缀配置，则原样返回
    """
    try:
        prefix_map = AsymmetricCipherSelector(using=using).get_init_config().prefix_cipher_type_map
    except Exception:
        return ciphertext

    for prefix in prefix_map:
        if not ciphertext.startswith(prefix):
            continue
        trusted_value = ciphertext[len(prefix) :]
        # hex 形态判定：非空、偶数长度、且全部为十六进制字符
        if len(trusted_value) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", trusted_value):
            return ciphertext
        try:
            ciphertext_bytes = bytes.fromhex(trusted_value)
        except ValueError:
            return ciphertext
        return prefix + base64.b64encode(ciphertext_bytes).decode(encoding="utf-8")

    return ciphertext


def decrypt(ciphertext: str, using: typing.Optional[str] = None) -> str:
    """
    解密密码变量，密文格式为 `{prefix}{ciphertext}`，如 `rsa_str:::xxx...`

    密文体支持 base64（标准格式）与 hex（前端未做编码转换时）两种编码。

    :param ciphertext: 带算法前缀的密文
    :param using: bkcrypto 中的实例名
    :raises ValueError: 解密失败（无前缀、密文损坏、密钥不匹配等）
    """
    using = using or "default"
    selector = AsymmetricCipherSelector(using=using)
    plaintext: str = selector.decrypt(ciphertext)

    # selector 在"未匹配到前缀"和"解密过程抛异常"两种情况下都会原样返回入参，
    # 此时尝试一次 hex -> base64 兜底，兼容前端未做编码转换就上报的 hex 密文
    if plaintext == ciphertext:
        candidate = _convert_hex_ciphertext_to_base64(ciphertext, using)
        if candidate != ciphertext:
            candidate_plaintext = selector.decrypt(candidate)
            # 兜底同样可能失败（原样返回），此时维持失败语义交由下方统一抛出
            plaintext = ciphertext if candidate_plaintext == candidate else candidate_plaintext

    # 前缀仍在说明解密失败，必须抛出，
    # 否则调用方会把带前缀的密文误当作明文透传给插件
    if plaintext == ciphertext:
        raise ValueError(f"decrypt failed, invalid ciphertext or mismatched key: {ciphertext[:32]}")

    return plaintext


def encrypt(plaintext: str, using: typing.Optional[str] = None) -> str:
    using = using or "default"
    return AsymmetricCipherSelector(using=using).encrypt(plaintext)
