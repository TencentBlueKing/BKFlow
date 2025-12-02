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


def detect_credential_type(content_obj):
    """
    根据凭证内容判断凭证类型

    :param content_obj: 解密后的凭证内容字典
    :return: 凭证类型字符串
    """
    if not content_obj or not isinstance(content_obj, dict):
        return "CUSTOM"

    keys = set(content_obj.keys())

    # BK_APP: 包含 bk_app_code 和 bk_app_secret，且没有其他字段（或只有这两个）
    if keys == {"bk_app_code", "bk_app_secret"}:
        return "BK_APP"

    # BK_ACCESS_TOKEN: 包含 access_token，且没有其他字段（或只有这一个）
    if keys == {"access_token"}:
        return "BK_ACCESS_TOKEN"

    # BASIC_AUTH: 包含 username 和 password，且没有其他字段（或只有这两个）
    if keys == {"username", "password"}:
        return "BASIC_AUTH"

    # 其他情况或无法确定，使用自定义
    return "CUSTOM"


def set_credential_type_from_content(apps, schema_editor):
    """
    根据凭证内容设置凭证类型

    :param apps: Django apps registry
    :param schema_editor: 数据库 schema 编辑器
    """
    Credential = apps.get_model("space", "Credential")
    table_name = Credential._meta.db_table
    crypt = BaseCrypt(instance_key=settings.PRIVATE_SECRET)

    # 统计信息
    total_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0

    print("\n开始根据凭证内容设置凭证类型...")

    def is_value_encrypted(raw_value: str) -> bool:
        """
        判断值是否已加密
        """
        if not isinstance(raw_value, str) or not raw_value:
            return False
        try:
            plain = crypt.decrypt(raw_value)
            re_encrypted = crypt.encrypt(plain)
            return re_encrypted == raw_value
        except Exception:
            return False

    def decrypt_content(raw_content):
        """
        解密凭证内容

        :param raw_content: 原始内容（可能是加密的 JSON 字符串或字典）
        :return: 解密后的内容字典
        """
        # 解析 JSON
        try:
            content_obj = (
                raw_content if isinstance(raw_content, dict) else json.loads(raw_content) if raw_content else None
            )
        except Exception:
            content_obj = None

        if not content_obj or not isinstance(content_obj, dict):
            return None

        # 解密每个值
        decrypted_content = {}
        for key, value in content_obj.items():
            if value is not None and isinstance(value, str):
                # 尝试解密
                if is_value_encrypted(value):
                    try:
                        decrypted_content[key] = crypt.decrypt(value)
                    except Exception:
                        # 解密失败，使用原值（可能是未加密的旧数据）
                        decrypted_content[key] = value
                else:
                    # 未加密，直接使用
                    decrypted_content[key] = value
            else:
                decrypted_content[key] = value

        return decrypted_content

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id, name, type, content FROM {connection.ops.quote_name(table_name)}")
        rows = cursor.fetchall()

    for row in rows:
        total_count += 1
        cred_id, cred_name, cred_type, raw_content = row

        # 如果已经有类型且不是空字符串，跳过
        if cred_type and cred_type.strip():
            skipped_count += 1
            print(f"  跳过已有类型的凭证: ID={cred_id}, Name={cred_name}, Type={cred_type}")
            continue

        try:
            # 解密内容
            decrypted_content = decrypt_content(raw_content)

            if not decrypted_content:
                # 无法解析内容，设置为自定义
                detected_type = "CUSTOM"
            else:
                # 根据内容判断类型
                detected_type = detect_credential_type(decrypted_content)

            # 更新类型
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {connection.ops.quote_name(table_name)} SET type=%s WHERE id=%s",
                    [detected_type, cred_id],
                )

            updated_count += 1
            print(f"  ✓ 成功设置凭证类型: ID={cred_id}, Name={cred_name}, Type={detected_type}")

        except Exception as e:
            error_count += 1
            print(f"  ✗ 设置凭证类型失败: ID={cred_id}, Name={cred_name}, Error={str(e)}")

    # 打印统计信息
    print("\n" + "=" * 70)
    print("凭证类型设置完成！")
    print(f"  总计: {total_count} 条")
    print(f"  已更新: {updated_count} 条")
    print(f"  已跳过: {skipped_count} 条（已有类型或空数据）")
    print(f"  失败: {error_count} 条")
    print("=" * 70 + "\n")


def reverse_set_credential_type(apps, schema_editor):
    """
    回滚操作：将凭证类型设置为 CUSTOM（因为无法确定原始类型）

    :param apps: Django apps registry
    :param schema_editor: 数据库 schema 编辑器
    """
    Credential = apps.get_model("space", "Credential")
    table_name = Credential._meta.db_table

    print("\n开始回滚：将凭证类型设置为 CUSTOM...")
    print("注意：回滚操作会将所有凭证类型设置为 CUSTOM，因为无法确定原始类型")

    with connection.cursor() as cursor:
        cursor.execute(f"UPDATE {connection.ops.quote_name(table_name)} SET type='CUSTOM'")
        affected_rows = cursor.rowcount

    print(f"\n回滚完成！已将 {affected_rows} 条凭证的类型设置为 CUSTOM\n")


class Migration(migrations.Migration):

    dependencies = [
        ("space", "0010_credential_scope_level"),
    ]

    operations = [
        migrations.RunPython(set_credential_type_from_content, reverse_set_credential_type),
    ]
