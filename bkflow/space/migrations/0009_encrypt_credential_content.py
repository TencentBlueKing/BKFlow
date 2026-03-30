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
import json

from django.conf import settings
from django.db import connection, migrations

from bkflow.utils.crypt import BaseCrypt


def encrypt_existing_credentials(apps, schema_editor):
    """
    加密已存在的未加密凭证数据

    :param apps: Django apps registry
    :param schema_editor: 数据库 schema 编辑器
    """
    Credential = apps.get_model("space", "Credential")
    table_name = Credential._meta.db_table
    crypt = BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    # 统计信息
    total_count = 0
    encrypted_count = 0
    skipped_count = 0
    error_count = 0

    print("\n开始检查并加密未加密的凭证数据...")

    def is_value_encrypted(raw_value: str) -> bool:
        """
        通过解密并重新加密后与原始密文比对，判断是否为本系统的加密值。
        说明：BaseCrypt 的加解密在相同 KEY/IV 下是确定性的，因此 encrypt(decrypt(x)) == x 成立。
        """
        if not isinstance(raw_value, str) or not raw_value:
            return False
        try:
            plain = crypt.decrypt(raw_value)
            re_encrypted = crypt.encrypt(plain)
            return re_encrypted == raw_value
        except Exception:
            return False

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id, name, type, content FROM {connection.ops.quote_name(table_name)}")
        rows = cursor.fetchall()

    for row in rows:
        total_count += 1
        cred_id, cred_name, cred_type, raw_content = row

        # 解析原始 content（以数据库中的原样字符串/JSON存储为准）
        try:
            content_obj = (
                raw_content if isinstance(raw_content, dict) else json.loads(raw_content) if raw_content else None
            )
        except Exception:
            content_obj = None

        if not content_obj or not isinstance(content_obj, dict):
            skipped_count += 1
            continue

        try:
            updated = False
            encrypted_content = {}
            for key, value in content_obj.items():
                if value is not None and isinstance(value, str):
                    # 已是密文则保持原样；否则进行加密
                    if is_value_encrypted(value):
                        encrypted_content[key] = value
                    else:
                        encrypted_content[key] = crypt.encrypt(value)
                        updated = True
                else:
                    encrypted_content[key] = value

            if not updated:
                skipped_count += 1
                print(f"  跳过已加密的凭证: ID={cred_id}, Name={cred_name}")
                continue

            # 直接以原生 SQL 更新，避免字段 from_db_value/to_python 的再次处理
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {connection.ops.quote_name(table_name)} SET content=%s WHERE id=%s",
                    [json.dumps(encrypted_content), cred_id],
                )

            encrypted_count += 1
            print(f"  ✓ 成功加密凭证: ID={cred_id}, Name={cred_name}, Type={cred_type}")

        except Exception as e:
            error_count += 1
            print(f"  ✗ 加密失败: ID={cred_id}, Name={cred_name}, Error={str(e)}")

    # 打印统计信息
    print("\n" + "=" * 70)
    print("凭证数据加密完成！")
    print(f"  总计: {total_count} 条")
    print(f"  已加密: {encrypted_count} 条")
    print(f"  已跳过: {skipped_count} 条（已加密或空数据）")
    print(f"  失败: {error_count} 条")
    print("=" * 70 + "\n")


def reverse_encrypt(apps, schema_editor):
    """
    回滚操作：解密已加密的凭证数据

    :param apps: Django apps registry
    :param schema_editor: 数据库 schema 编辑器
    """
    Credential = apps.get_model("space", "Credential")
    table_name = Credential._meta.db_table
    crypt = BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    print("\n开始回滚：解密凭证数据...")

    decrypted_count = 0
    error_count = 0

    def is_value_encrypted(raw_value: str) -> bool:
        if not isinstance(raw_value, str) or not raw_value:
            return False
        try:
            plain = crypt.decrypt(raw_value)
            # 与加密迁移中相同的判定策略
            return crypt.encrypt(plain) == raw_value
        except Exception:
            return False

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id, name, content FROM {connection.ops.quote_name(table_name)}")
        rows = cursor.fetchall()

    for row in rows:
        cred_id, cred_name, raw_content = row
        try:
            content_obj = (
                raw_content if isinstance(raw_content, dict) else json.loads(raw_content) if raw_content else None
            )
        except Exception:
            content_obj = None
        if not content_obj or not isinstance(content_obj, dict):
            continue

        try:
            updated = False
            decrypted_content = {}
            for key, value in content_obj.items():
                if value is not None and isinstance(value, str) and is_value_encrypted(value):
                    decrypted_content[key] = crypt.decrypt(value)
                    updated = True
                else:
                    decrypted_content[key] = value

            if not updated:
                continue

            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {connection.ops.quote_name(table_name)} SET content=%s WHERE id=%s",
                    [json.dumps(decrypted_content), cred_id],
                )
            decrypted_count += 1
            print(f"  ✓ 成功解密凭证: ID={cred_id}, Name={cred_name}")

        except Exception as e:
            error_count += 1
            print(f"  ✗ 解密失败: ID={cred_id}, Name={cred_name}, Error={str(e)}")

    print(f"\n回滚完成！解密 {decrypted_count} 条，失败 {error_count} 条\n")


class Migration(migrations.Migration):

    dependencies = [
        ("space", "0008_auto_20251014_1511"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_credentials, reverse_encrypt),
    ]
