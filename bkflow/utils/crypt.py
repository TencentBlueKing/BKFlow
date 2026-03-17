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
