"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

We undertake not to change the open source license (MIT license) applicable

to the current version of the project delivered to anyone in the future.

票据签发、续期、撤销与请求内有效性读取。
"""

from datetime import timedelta
from typing import Iterator, Optional, Sequence, Tuple

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from pytimeparse import parse

from bkflow.permission.grants import Grant, canonical_grants, grant_hash, grant_set_hash
from bkflow.permission.models import Token, TokenGrant
from bkflow.space.configs import TokenAutoRenewalConfig, TokenExpirationConfig
from bkflow.space.models import SpaceConfig


def _renew_locked_token(token, user, expiration_seconds=None, auto_renewal=None):
    """持有主票据行锁时重新校验，再按空间配置更新整个票据。"""
    now = timezone.now()
    if token is None or token.expired_time <= now:
        return False, "Token 已过期或不存在", token
    if user is not None and token.user != user:
        return False, "Token 续期失败，当前续期的用户与正在登录的用户不一致", token
    if not token.get_grants():
        return False, "Token 授权不完整", token

    if auto_renewal is None:
        auto_renewal = SpaceConfig.get_config(token.space_id, TokenAutoRenewalConfig.name) == "true"
    if not auto_renewal:
        return False, "续期失败，当前空间未开启token自动续期", token
    if expiration_seconds is None:
        expiration_seconds = parse(SpaceConfig.get_config(token.space_id, TokenExpirationConfig.name))

    # 配置和明细查询也可能跨过到期边界；实际写入前仍须有效。
    now = timezone.now()
    if token.expired_time <= now:
        return False, "Token 已过期或不存在", token
    token.expired_time = now + timedelta(seconds=expiration_seconds)
    token.save(update_fields=["expired_time"])
    return True, "", token


def _lock_token_candidates(token_ids):
    """统一按主键顺序锁主行，避免二级有效期索引与主行的反向锁等待。"""
    return list(Token.objects.select_for_update().filter(pk__in=token_ids).order_by("pk"))


def issue_token(space_id, user, grants: Sequence[Grant], expiration_seconds, auto_renewal) -> Token:
    """签发已完成资源校验的授权集合，原子复用或创建完整票据。"""
    grants = canonical_grants(grants)
    if not grants:
        raise ValueError("授权集合不能为空")
    # 与 IntegerField 查询转换保持一致；资源 ID 仍保留字符串身份。
    space_id = Token._meta.get_field("space_id").get_prep_value(space_id)
    composite = len(grants) > 1
    storage_fields = (
        {"grant_set_hash": grant_set_hash(grants)}
        if composite
        else {"grant_set_hash__isnull": True, **grants[0].as_dict()}
    )
    with transaction.atomic():
        # 候选发现不加二级索引锁；所有生命周期写入先按相同顺序锁主键。
        candidate_ids = list(
            Token.objects.filter(
                space_id=space_id, user=user, expired_time__gt=timezone.now(), **storage_fields
            ).values_list("pk", flat=True)
        )
        candidates = _lock_token_candidates(candidate_ids)
        # 锁顺序不决定复用优先级；在持锁后的最新数据中仍选择最晚过期者。
        candidates.sort(key=lambda token: token.pk)
        candidates.sort(key=lambda token: token.expired_time, reverse=True)
        for token in candidates:
            if (
                token.has_expired()
                or token.user != user
                or token.space_id != space_id
                or token.is_composite != composite
                or token.get_grants() != grants
            ):
                continue
            if auto_renewal:
                result, _, token = _renew_locked_token(token, user, expiration_seconds, auto_renewal)
                if not result:
                    continue
            elif token.has_expired():
                continue
            return token

        token = Token.objects.create(
            token=Token.generate_token(),
            space_id=space_id,
            user=user,
            expired_time=timezone.now() + timedelta(seconds=expiration_seconds),
            grant_set_hash=storage_fields["grant_set_hash"] if composite else None,
            **({"resource_type": "", "resource_id": "", "permission_type": ""} if composite else grants[0].as_dict()),
        )
        if composite:
            TokenGrant.objects.bulk_create(
                [TokenGrant(token=token, grant_hash=grant_hash(grant), **grant.as_dict()) for grant in grants]
            )
        return token


def renew_token(token_id, user=None) -> Tuple[bool, str, Optional[Token]]:
    """锁定并重新读取票据后续期，不恢复已撤销或已到期的票据。"""
    with transaction.atomic():
        token = Token.objects.select_for_update().filter(pk=token_id).first()
        return _renew_locked_token(token, user)


def revoke_tokens(space_id, filters: dict) -> int:
    """按完整授权条件筛选并撤销整张票据，返回不同主票据数量。"""
    resource_fields = {"resource_type", "resource_id", "permission_type"}
    resource_filters = {key: value for key, value in filters.items() if key in resource_fields}
    main_filters = {key: value for key, value in filters.items() if key not in resource_fields}
    tokens = Token.objects.filter(space_id=space_id).filter(**main_filters)
    if resource_filters:
        # EXISTS 保证所有资源条件落在同一条明细，也避免多条匹配产生重复主行。
        matching_grants = TokenGrant.objects.filter(token_id=OuterRef("pk"), **resource_filters)
        tokens = tokens.annotate(has_matching_grant=Exists(matching_grants)).filter(
            Q(grant_set_hash__isnull=True, **resource_filters)
            | Q(grant_set_hash__isnull=False, has_matching_grant=True)
        )
    with transaction.atomic():
        candidate_ids = list(tokens.values_list("pk", flat=True))
        locked = _lock_token_candidates(candidate_ids)
        # 持锁后重新核对原过滤条件；删除或不再匹配的候选不纳入计数。
        token_ids = list(tokens.filter(pk__in=[token.pk for token in locked]).values_list("pk", flat=True))
        return Token.objects.filter(pk__in=token_ids).update(expired_time=timezone.now())


def get_valid_token(token_id, user, space_id=None, request=None) -> Optional[Token]:
    """读取当前身份空间内的有效完整票据，仅在同一请求内复用数据库读取。"""
    if space_id is not None:
        space_id = Token._meta.get_field("space_id").get_prep_value(space_id)
    cache_key = (token_id, user, space_id)
    cache = None
    if request is not None:
        cache = getattr(request, "_bkflow_valid_token_cache", None)
        if cache is None:
            cache = request._bkflow_valid_token_cache = {}
    if cache is not None and cache_key in cache:
        token = cache[cache_key]
    else:
        tokens = Token.objects.filter(pk=token_id, user=user)
        if space_id is not None:
            tokens = tokens.filter(space_id=space_id)
        token = tokens.prefetch_related("grants").first()
        if cache is not None:
            cache[cache_key] = token

    if token is None or token.user != user or token.expired_time <= timezone.now():
        return None
    if space_id is not None and token.space_id != space_id:
        return None
    if not token.get_grants():
        return None
    return token


def iter_user_grants(space_id, user, resource_selectors) -> Iterator[Grant]:
    """批量读取当前用户空间内相关票据，完整性验证后仅投影匹配授权。"""
    selectors = {(resource_type, str(resource_id)) for resource_type, resource_id in resource_selectors}
    if not selectors:
        return
    resource_filter = Q()
    for resource_type, resource_id in selectors:
        resource_filter |= Q(resource_type=resource_type, resource_id=resource_id)
    matching_grants = TokenGrant.objects.filter(resource_filter, token_id=OuterRef("pk"))
    tokens = (
        Token.objects.filter(space_id=space_id, user=user, expired_time__gt=timezone.now())
        .annotate(has_matching_grant=Exists(matching_grants))
        .filter(
            Q(grant_set_hash__isnull=True) & resource_filter | Q(grant_set_hash__isnull=False, has_matching_grant=True)
        )
        .prefetch_related("grants")
    )
    for token in tokens:
        # 数据库排序规则可能忽略大小写；鉴权仍严格绑定登录身份。
        if token.user != user or token.has_expired():
            continue
        for grant in token.get_grants():
            if (grant.resource_type, grant.resource_id) in selectors:
                yield grant
