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
"""

import logging

from bkflow.plugin_catalog.models import CatalogChangeRecord, CatalogChangeSource

logger = logging.getLogger(__name__)


class CatalogChangeRecordService:
    """
    插件目录变更记录的写入入口（本期只写不读：无查询接口、无审计页面）。

    设计文档明确「不新增审计页面」，因此本服务只提供写入能力，数据用于：
    - 排障追溯："这个插件为什么用不了了、是谁改的"
    - 上线回退核对：用初始化结果 + 变更记录做差异核对

    写入一律在调用方的事务内完成，保证「业务数据已生效但变更记录丢了」不会发生；
    写入失败会让业务事务一起回滚（与设计文档"同库事务…异常整笔回滚"一致），
    如需改成"审计失败不阻断业务"，把 fail_silently 传 True 即可。
    """

    @classmethod
    def record(
        cls,
        space_id,
        instance_id,
        operate_type,
        operator,
        before_value=None,
        after_value=None,
        method="",
        reason="",
        request_id="",
        operate_source=CatalogChangeSource.WEB,
        fail_silently=False,
    ):
        """
        写一条变更记录。

        :param space_id: 空间 ID
        :param instance_id: 变更对象实例 ID（插件条目 id / 目录 id / 空间 id）
        :param operate_type: CatalogChangeType 中的操作类型
        :param operator: 操作人
        :param before_value: 变更前值（JSON 可序列化）
        :param after_value: 变更后值（JSON 可序列化）
        :param method: 触发的操作方法名（如 plugins/status）
        :param reason: 变更原因（下架原因等）
        :param request_id: 请求链路 ID，便于与网关/前端日志对齐
        :param operate_source: CatalogChangeSource 中的操作来源
        :param fail_silently: True 时写入失败只记日志、不影响业务事务
        """
        try:
            return CatalogChangeRecord.objects.create(
                space_id=space_id,
                instance_id=instance_id,
                operate_type=operate_type,
                operate_source=operate_source,
                operator=operator or "",
                before_value=before_value or {},
                after_value=after_value or {},
                method=method,
                reason=reason or "",
                request_id=request_id or "",
            )
        except Exception:
            logger.exception(
                "插件目录变更记录写入失败: space_id=%s, operate_type=%s, instance_id=%s",
                space_id,
                operate_type,
                instance_id,
            )
            if fail_silently:
                return None
            raise

    @classmethod
    def record_entry_change(cls, space_id, entry, before_value, operate_type, operator, **kwargs):
        """记录单个插件条目的变更：前后值统一由条目快照生成，避免各调用点口径不一。"""
        return cls.record(
            space_id=space_id,
            instance_id=entry.id,
            operate_type=operate_type,
            operator=operator,
            before_value=before_value,
            after_value=cls.entry_snapshot(entry),
            **kwargs,
        )

    @staticmethod
    def entry_snapshot(entry):
        """插件条目关键字段快照，作为变更记录的前后值。"""
        return {
            "plugin_type": entry.plugin_type,
            "source_key": entry.source_key,
            "plugin_code": entry.plugin_code,
            "status": entry.status,
            "directory_id": entry.directory_id,
            "recommended": entry.recommended,
            "recommend_order": entry.recommend_order,
            "disable_config": entry.disable_config or {},
            "offline_reason": entry.offline_reason,
            "replace_plugin_id": entry.replace_plugin_id,
        }
