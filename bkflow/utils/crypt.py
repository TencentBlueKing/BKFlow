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
import base64

from Crypto.Cipher import AES
from django.conf import settings


class BaseCrypt:
    _bk_crypt = False

    # KEY 和 IV 的长度需等于16
    ROOT_KEY = b"TencentBkApp-Key"
    ROOT_IV = b"TencentBkApp--Iv"
    encoding = None

    def __init__(self, instance_key=settings.SECRET_KEY, encoding="utf-8"):
        self.INSTANCE_KEY = instance_key
        self.encoding = encoding

    def encrypt(self, plaintext):
        """
        加密
        :param plaintext: 需要加密的内容
        :return:
        """
        decrypt_key = self.__parse_key()
        if isinstance(plaintext, str):
            plaintext = plaintext.encode(encoding=self.encoding)
        secret_txt = AES.new(decrypt_key, AES.MODE_CFB, self.ROOT_IV).encrypt(plaintext)
        return base64.b64encode(secret_txt).decode("utf-8")

    def decrypt(self, ciphertext):
        """
        解密
        :param ciphertext: 需要解密的内容
        :return:
        """
        decrypt_key = self.__parse_key()
        # 先解base64
        secret_txt = base64.b64decode(ciphertext)
        # 再解对称加密
        plain = AES.new(decrypt_key, AES.MODE_CFB, self.ROOT_IV).decrypt(secret_txt)
        return plain.decode(encoding=self.encoding)

    def __parse_key(self):
        return self.INSTANCE_KEY[:24].encode()


class CredentialCrypt(BaseCrypt):
    """按部署配置写入 SM4-GCM，始终兼容无前缀的历史 AES 密文。"""

    SM4_PREFIX = "bkflow:sm4:gcm:v1:"

    def _sm4_cipher(self):
        """用 SM3 从稳定的部署密钥派生 SM4 密钥，由 SDK 生成随机 nonce 和认证标签。"""
        from bkcrypto.constants import SymmetricMode
        from bkcrypto.contrib.basic.ciphers import get_symmetric_cipher
        from bkcrypto.symmetric.options import SM4SymmetricOptions
        from tongsuopy.crypto import hashes

        digest = hashes.Hash(hashes.SM3())
        digest.update(b"bkflow-credential-sm4-v1\x00" + self.INSTANCE_KEY.encode("utf-8"))
        return get_symmetric_cipher(
            "SM4",
            common={"key": digest.finalize()[:16]},
            cipher_options={"SM4": SM4SymmetricOptions(mode=SymmetricMode.GCM)},
        )

    def encrypt(self, plaintext):
        """算法配置只影响新写入；AES 模式保留旧版本可读的原始格式。"""
        if settings.BKFLOW_CREDENTIAL_CIPHER == "SM4":
            return self.SM4_PREFIX + self._sm4_cipher().encrypt(plaintext)
        return super().encrypt(plaintext)

    def decrypt(self, ciphertext):
        """根据密文自身标识选择算法，切换写入配置后仍能读回两种格式。"""
        if isinstance(ciphertext, str) and ciphertext.startswith(self.SM4_PREFIX):
            return self._sm4_cipher().decrypt(ciphertext[len(self.SM4_PREFIX) :])
        return super().decrypt(ciphertext)
