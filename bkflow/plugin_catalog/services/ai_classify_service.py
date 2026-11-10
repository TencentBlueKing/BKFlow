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

import logging

logger = logging.getLogger(__name__)


class AiClassifyService:
    """
    AI 智能分类服务，统一供以下三处调用：
    - 06 新插件策略"全部直接通过 / AI 自动决定分类"、"设条件自动通过"条件组里 after_pass=ai
      （由 apply_automatic_classification_task 异步调用，增量/自由范围见 ai_scope）
    - 08 目录批量管理"AI 智能分类"（人工手动触发，仅返回建议，不落库）

    仓库内当前没有 bkaidev 客户端代码/接入凭证，本服务把"请求 AI 模型拿分类建议"这一步
    收敛到 `_request_classification` 单一方法，先返回 empty 占位，保证上层（同步落位任务、
    后续 08 接口）的调用契约和异常处理路径可以正常跑通；接入真实 bkaidev 后只需要替换这一个
    方法的实现，不影响调用方代码。
    """

    RESULT_PATCH = "patch"
    RESULT_EMPTY = "empty"
    RESULT_ERROR = "error"

    @classmethod
    def classify(cls, space_id, plugin_keys, ai_scope, request_id=None):
        """
        对给定插件身份列表请求 AI 分类建议。

        :param space_id: 空间 ID
        :param plugin_keys: list[str]，格式 "{plugin_type}:{source_key}:{plugin_code}"
        :param ai_scope: "increment" | "free"
        :param request_id: 幂等标识，供调用方去重
        :return: {"result": "patch"|"empty"|"error", "patch": {plugin_key: directory_id}, "message": str}
        """
        if not plugin_keys:
            return {"result": cls.RESULT_EMPTY, "patch": {}, "message": ""}
        try:
            return cls._request_classification(
                space_id=space_id, plugin_keys=plugin_keys, ai_scope=ai_scope, request_id=request_id
            )
        except Exception as exc:  # noqa: BLE001 对接真实 bkaidev 前统一兜底，不让未知异常中断调用方流程
            logger.exception("AI 智能分类请求失败: space_id=%s, request_id=%s", space_id, request_id)
            return {"result": cls.RESULT_ERROR, "patch": {}, "message": str(exc)}

    @classmethod
    def _request_classification(cls, space_id, plugin_keys, ai_scope, request_id):
        # TODO(bkaidev 接入): 当前返回空建议占位。真实接入时在这里调用 bkaidev 客户端，
        # 传入插件名称/描述等上下文，解析响应为 {plugin_key: directory_id} 后返回
        # {"result": RESULT_PATCH, "patch": {...}, "message": ""}。
        logger.warning(
            "AI 智能分类尚未接入真实 bkaidev，返回空建议: space_id=%s, plugin_count=%s, ai_scope=%s",
            space_id,
            len(plugin_keys),
            ai_scope,
        )
        return {"result": cls.RESULT_EMPTY, "patch": {}, "message": "AI 分类服务尚未接入"}
