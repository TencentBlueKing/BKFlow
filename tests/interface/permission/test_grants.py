import dataclasses

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone


def test_grant_is_immutable_and_serializes_resource_identity():
    """Grant 应保持完整三元组并禁止原地修改。"""
    from bkflow.permission.grants import Grant

    grant = Grant(resource_type="TEMPLATE", resource_id="001", permission_type="MOCK")

    assert grant.as_dict() == {
        "resource_type": "TEMPLATE",
        "resource_id": "001",
        "permission_type": "MOCK",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        grant.resource_id = "1"


def test_canonical_grants_deduplicates_and_sorts_complete_grants():
    """规范化应按完整三元组排序，并移除完全重复项。"""
    from bkflow.permission.grants import Grant, canonical_grants

    grants = [
        Grant(resource_type="TEMPLATE", resource_id="001", permission_type="MOCK"),
        Grant(resource_type="TASK", resource_id="2", permission_type="OPERATE"),
        Grant(resource_type="TEMPLATE", resource_id="001", permission_type="MOCK"),
    ]

    assert [grant.as_dict() for grant in canonical_grants(grants)] == [
        {"resource_type": "TASK", "resource_id": "2", "permission_type": "OPERATE"},
        {"resource_type": "TEMPLATE", "resource_id": "001", "permission_type": "MOCK"},
    ]


def test_grant_hash_uses_versioned_compact_json():
    """单项摘要应覆盖版本和完整授权三元组。"""
    from bkflow.permission.grants import Grant, grant_hash

    grant = Grant(resource_type="TEMPLATE", resource_id="001", permission_type="MOCK")

    assert grant_hash(grant) == "8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d"


def test_grant_set_hash_is_order_and_duplicate_independent():
    """集合摘要应基于排序去重后的完整授权集合。"""
    from bkflow.permission.grants import Grant, grant_set_hash

    template_grant = Grant(resource_type="TEMPLATE", resource_id="001", permission_type="MOCK")
    task_grant = Grant(resource_type="TASK", resource_id="2", permission_type="OPERATE")

    assert (
        grant_set_hash([template_grant, task_grant, template_grant])
        == "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14"
    )
    assert (
        grant_set_hash([task_grant, template_grant])
        == "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14"
    )


def test_unicode_hashes_use_ascii_escapes_including_surrogate_pair():
    """固定中文和非 BMP 字符的 JSON 字节契约，便于跨语言实现核对。"""
    from bkflow.permission.grants import Grant, grant_hash, grant_set_hash

    grant = Grant("SCOPE", "biz_中文🚀", "VIEW")
    assert grant_hash(grant) == "b7c4a7bad44b6e66801f47a0aa3029cb8d7adb2b0229a5bd61f109cba38411cf"
    assert (
        grant_set_hash([Grant("TASK", "200", "OPERATE"), grant, grant])
        == "5a16e4bf49ca742839b70002b097fb34523956e37ee9da6ec843dbcb17e160da"
    )


@pytest.mark.django_db
def test_single_grant_uses_detail_storage_and_legacy_response():
    """单项票据应只存一条完整明细，并重建旧成功响应字段。"""
    from bkflow.permission.grants import Grant, grant_set_hash
    from bkflow.permission.models import Token
    from bkflow.permission.services import issue_token

    grant = Grant("TEMPLATE", "001", "MOCK")
    token = issue_token(1, "alice", (grant,), 3600, False)

    assert token.grants.count() == 1
    assert token.grant_set_hash == grant_set_hash(token.get_grants())
    assert not {"resource_type", "resource_id", "permission_type"} & {field.name for field in Token._meta.fields}
    assert token.to_json()["resource_id"] == "001"
    assert token.is_composite is False


def _create_composite_token(token_id, grant_set_digest):
    from bkflow.permission.models import Token

    return Token.objects.create(
        token=token_id,
        space_id=1,
        user="alice",
        grant_set_hash=grant_set_digest,
        expired_time=timezone.now(),
    )


def _create_valid_grants(token):
    from bkflow.permission.models import TokenGrant

    TokenGrant.objects.bulk_create(
        [
            TokenGrant(
                token=token,
                resource_type="TEMPLATE",
                resource_id="001",
                permission_type="MOCK",
                grant_hash="8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
            ),
            TokenGrant(
                token=token,
                resource_type="TASK",
                resource_id="2",
                permission_type="OPERATE",
                grant_hash="b1fdc051e73534b2904f9afd5e389855d29172e3ca3a0396506879049891d140",
            ),
        ]
    )


@pytest.mark.django_db
def test_composite_grants_use_only_valid_canonical_details():
    """组合票据应只返回经过完整性校验并规范排序的明细。"""
    token = _create_composite_token(
        "composite",
        "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14",
    )
    _create_valid_grants(token)

    assert token.is_composite is True
    assert [grant.as_dict() for grant in token.get_grants()] == [
        {"resource_type": "TASK", "resource_id": "2", "permission_type": "OPERATE"},
        {"resource_type": "TEMPLATE", "resource_id": "001", "permission_type": "MOCK"},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("detail_count", [0, 1])
def test_composite_grants_reject_fewer_than_two_details(detail_count):
    """组合票据缺少明细或只有一项时应拒绝全部授权。"""
    from bkflow.permission.models import TokenGrant

    token = _create_composite_token(
        f"too-few-{detail_count}",
        "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14",
    )
    if detail_count:
        TokenGrant.objects.create(
            token=token,
            resource_type="TEMPLATE",
            resource_id="001",
            permission_type="MOCK",
            grant_hash="8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
        )

    assert token.get_grants() == ()


@pytest.mark.django_db
def test_composite_grants_reject_incorrect_item_hash():
    """任一明细摘要错误时应拒绝整张组合票据。"""
    from bkflow.permission.models import TokenGrant

    token = _create_composite_token(
        "bad-item-hash",
        "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14",
    )
    _create_valid_grants(token)
    TokenGrant.objects.filter(token=token, resource_type="TASK").update(grant_hash="0" * 64)

    assert token.get_grants() == ()


@pytest.mark.django_db
def test_composite_grants_reject_incorrect_set_hash():
    """主表集合摘要错误时应拒绝整张组合票据。"""
    token = _create_composite_token("bad-set-hash", "0" * 64)
    _create_valid_grants(token)

    assert token.get_grants() == ()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("token_id", "grant_set_digest", "details"),
    [
        (
            "invalid-resource-type",
            "023a9535e1500365afe2c43385ae49aa149075bd60ce97d6f10983ce7f849fac",
            [
                ("NOPE", "1", "VIEW", "c85a1f091822221d59748f0871abb3675a9f6b896e6d73dadd4c3d2b70aa0429"),
                ("TASK", "2", "OPERATE", "b1fdc051e73534b2904f9afd5e389855d29172e3ca3a0396506879049891d140"),
            ],
        ),
        (
            "blank-resource-id",
            "57e16d58d331de5ce13114351e865ae0c318431d0d210ed6b1632ed748f4aad2",
            [
                ("TASK", "", "VIEW", "8a331da8bb437edaa6e900a982cbdf42b4fb5ba86aa292263963f8bacdea2fd3"),
                ("TEMPLATE", "1", "MOCK", "7398e0c8cb1f2ffa54af1d7040d7b3065389d91ca5c267b5eb5c84c0b511ac03"),
            ],
        ),
        (
            "invalid-permission-type",
            "255276f7b537f0914a468481e1a1648e0981e56d7ef844497bef643fd74067e4",
            [
                ("TASK", "1", "NOPE", "316a3aabae76645f1bc30d2605592d31ed7fe7022b8a3eb5312d8c68d13ae55f"),
                ("TEMPLATE", "2", "MOCK", "170c46da75c87fee2b5fc1aaec009f9267ac1b18fe3771c74f09ab38f066269f"),
            ],
        ),
    ],
)
def test_composite_grants_reject_invalid_fields(token_id, grant_set_digest, details):
    """摘要正确但字段或枚举非法的组合明细也应拒绝授权。"""
    from bkflow.permission.models import TokenGrant

    token = _create_composite_token(token_id, grant_set_digest)
    TokenGrant.objects.bulk_create(
        [
            TokenGrant(
                token=token,
                resource_type=resource_type,
                resource_id=resource_id,
                permission_type=permission_type,
                grant_hash=grant_digest,
            )
            for resource_type, resource_id, permission_type, grant_digest in details
        ]
    )

    assert token.get_grants() == ()


@pytest.mark.django_db
def test_token_grant_is_deleted_with_token():
    """删除主票据时应级联删除其授权明细。"""
    from bkflow.permission.models import TokenGrant

    token = _create_composite_token(
        "cascade",
        "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14",
    )
    _create_valid_grants(token)

    token.delete()

    assert TokenGrant.objects.filter(token_id="cascade").count() == 0


@pytest.mark.django_db
def test_token_grant_rejects_duplicate_hash_for_same_token():
    """同一票据不能保存重复的单项摘要。"""
    from bkflow.permission.models import TokenGrant

    token = _create_composite_token(
        "duplicate-hash",
        "36ac11a0e9ffe6c90a5f8082dfba13992d11ef0d4cb6e3067dbf32bdac925b14",
    )
    detail = {
        "token": token,
        "resource_type": "TEMPLATE",
        "resource_id": "001",
        "permission_type": "MOCK",
        "grant_hash": "8085619d6b64b06d4ce5569c9be08f04911470d1f3cf62c32f633a4b54f2219d",
    }
    TokenGrant.objects.create(**detail)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TokenGrant.objects.create(**detail)
