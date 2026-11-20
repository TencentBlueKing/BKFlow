"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸流程引擎服务 (BlueKing Flow Engine Service) available.
Copyright (C) 2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (see LICENSE for details).
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger("root")


class AiAgentClient:
    """
    aidev 智能体调用客户端。

    智能体是**固定配置**的（不随空间变化），用户侧不暴露、也不允许配置，
    因此应用凭证与调用身份统一走环境变量：

    - `PLUGIN_CATALOG_AI_APP_CODE`：智能体所在的应用（APIGW 侧的应用 code）
    - `PLUGIN_CATALOG_AI_APP_SECRET`：该应用的密钥
    - `PLUGIN_CATALOG_AI_USERNAME`：调用身份（写入 `X-BKAIDEV-USER` 头）

    网关地址复用系统已有的 `BK_API_URL_TMPL`（与插件网关等其它 APIGW 调用同一个模板），
    只把 `{api_name}` 换成 `bp-{app_code}`。

    响应是 **SSE 流式**（`Content-Type: text/event-stream`），每个事件一行 `data: {json}`；
    模型输出在 `TEXT_MESSAGE_CONTENT` 事件的**顶层 `delta`** 字段（增量片段，按顺序拼接）。
    """

    # 智能体对话补全接口路径（挂在 `bp-{app_code}` 这个网关应用下）
    CHAT_COMPLETION_PATH = "/prod/bk_plugin/openapi/agent/chat_completion/"

    # 单次调用的默认超时（秒）。智能体是同步等待结果的，内部可能串行多步推理，给足时间。
    DEFAULT_TIMEOUT = 120

    TEXT_EVENT_TYPE = "TEXT_MESSAGE_CONTENT"

    class AgentNotConfigured(Exception):
        """环境变量未配置（应用凭证 / 调用身份缺失）。"""

    @classmethod
    def get_config(cls):
        """读智能体接入配置；缺配置直接报错，不静默降级。"""
        app_code = getattr(settings, "PLUGIN_CATALOG_AI_APP_CODE", "") or ""
        app_secret = getattr(settings, "PLUGIN_CATALOG_AI_APP_SECRET", "") or ""
        username = getattr(settings, "PLUGIN_CATALOG_AI_USERNAME", "") or ""
        missing = [
            name
            for name, value in (
                ("PLUGIN_CATALOG_AI_APP_CODE", app_code),
                ("PLUGIN_CATALOG_AI_APP_SECRET", app_secret),
                ("PLUGIN_CATALOG_AI_USERNAME", username),
            )
            if not value
        ]
        if missing:
            raise cls.AgentNotConfigured("智能体接入未配置，缺少环境变量: {}".format(", ".join(missing)))
        return {"app_code": app_code, "app_secret": app_secret, "username": username}

    @classmethod
    def build_url(cls, app_code):
        """拼智能体接口地址。

        默认复用系统已有的 `BK_API_URL_TMPL`（`{api_name}` 填 `bp-{app_code}`），
        与其它 APIGW 调用保持同一套地址来源；`PLUGIN_CATALOG_AI_APIGW_URL_TMPL`
        是**可选覆盖**——智能体所在应用挂在别的网关上时（比如开发环境的网关与
        生产不同），用它单独指定；不配置就回退到 `BK_API_URL_TMPL`。
        """
        url_tmpl = (
            getattr(settings, "PLUGIN_CATALOG_AI_APIGW_URL_TMPL", "")
            or getattr(settings, "BK_API_URL_TMPL", "")
            or ""
        )
        if not url_tmpl:
            raise cls.AgentNotConfigured("未配置 BK_API_URL_TMPL，无法拼接智能体接口地址")
        return "{}{}".format(url_tmpl.format(api_name="bp-{}".format(app_code)), cls.CHAT_COMPLETION_PATH)

    @classmethod
    def build_headers(cls, config):
        """APIGW 认证头：应用凭证 + 智能体调用身份。"""
        return {
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": json.dumps(
                {"bk_app_code": config["app_code"], "bk_app_secret": config["app_secret"]}
            ),
            "X-BKAIDEV-USER": config["username"],
        }

    @classmethod
    def build_payload(cls, prompt, thread_id=None):
        """请求体：`input` 是发给智能体的内容，`stream` 打开流式返回。

        `thread_id` 是智能体会话 id：传了之后智能体会读取该会话的历史记录，
        实现「用户接着追问」的多轮对话。
        """
        execute_kwargs = {"stream": True}
        if thread_id:
            execute_kwargs["thread_id"] = thread_id
        return {"chat_history": [], "execute_kwargs": execute_kwargs, "input": prompt}

    @classmethod
    def chat(cls, prompt, timeout=None, thread_id=None):
        """
        调智能体并返回**最终文本 + 会话 id**。

        :param prompt: 发给智能体的内容（自然语言指令）
        :param timeout: 单次请求超时（秒），默认 `DEFAULT_TIMEOUT`
        :param thread_id: 已有会话 id；传了就延续该会话（智能体读取历史记录）
        :return: `{"text": 智能体完整回复, "thread_id": 本次会话 id}`
        :raises AgentNotConfigured: 环境变量未配置
        :raises requests.RequestException: 网络 / 网关异常
        """
        config = cls.get_config()
        url = cls.build_url(config["app_code"])
        logger.info(
            "[智能体] 请求: url=%s, prompt_len=%s, thread_id=%s", url, len(prompt or ""), thread_id
        )
        response = requests.post(
            url,
            headers=cls.build_headers(config),
            json=cls.build_payload(prompt, thread_id=thread_id),
            timeout=timeout or cls.DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        # 响应的 Content-Type 是 text/event-stream 且**不带 charset**，requests 会按
        # ISO-8859-1 解码导致中文乱码，这里显式按 UTF-8 解码。
        raw = response.content.decode("utf-8", errors="replace")
        text = cls.parse_sse_text(raw)
        result = {"text": text, "thread_id": cls.parse_sse_thread_id(raw)}
        logger.info("[智能体] 响应: text_len=%s, thread_id=%s", len(text), result["thread_id"])
        return result

    THREAD_EVENT_TYPES = ("RUN_STARTED", "RUN_FINISHED")

    @classmethod
    def parse_sse_thread_id(cls, raw):
        """从 SSE 的 `RUN_STARTED` / `RUN_FINISHED` 事件里取会话 id（`threadId`）。

        后续用户追问时把这个 id 传回 `chat(thread_id=...)`，智能体会读取历史记录。
        """
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[len("data:") :].strip())
            except (TypeError, ValueError):
                continue
            if isinstance(event, dict) and event.get("type") in cls.THREAD_EVENT_TYPES:
                thread_id = event.get("threadId")
                if thread_id:
                    return thread_id
        return ""

    @classmethod
    def parse_sse_text(cls, raw):
        """从 SSE 流里提取模型输出的完整文本。

        每个事件是一行 `data: {json}`，模型输出在 `TEXT_MESSAGE_CONTENT` 事件的顶层
        `delta` 字段（增量片段，按出现顺序拼接）。其它事件（快照 / 步骤 / 结束）忽略。
        """
        chunks = []
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[len("data:") :].strip())
            except (TypeError, ValueError):
                # 心跳 / 非 JSON 行，忽略
                continue
            if not isinstance(event, dict) or event.get("type") != cls.TEXT_EVENT_TYPE:
                continue
            delta = event.get("delta")
            if delta:
                chunks.append(delta)
        return "".join(chunks)

