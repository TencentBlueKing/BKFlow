"""只读工具快照回放：不连接 BKFlow，仅在明确指定 variant 时调用本地模型。"""

import argparse
import base64
import copy
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import jsonschema
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENDPOINT = os.environ.get("HARNESS_REPLAY_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
MODEL = os.environ.get("HARNESS_REPLAY_MODEL", "local-model")
FIXTURE = None
SESSION = None
NODES = None
SNAPSHOT = None
SPACE_ID = None


def load_fixture(path, space_id):
    """载入调用方审核过的本地快照；不自动发现或上传任何环境证据。"""
    global FIXTURE, SESSION, NODES, SNAPSHOT, SPACE_ID
    FIXTURE = json.loads(path.read_text(encoding="utf-8"))
    SESSION = FIXTURE["base_artifact"]["session"]["session_id"]
    NODES = [node for page in FIXTURE["pages"] for node in page["items"]]
    SNAPSHOT = FIXTURE["pages"][0]["snapshot_id"]
    SPACE_ID = str(space_id)


def dump(value):
    """与服务端相同的紧凑 JSON 编码，不输出凭证。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encode(value):
    """编码不带填充的分页位置。"""
    return base64.urlsafe_b64encode(dump(value).encode()).decode().rstrip("=")


def normalize_schema(value):
    """转换 OpenAPI nullable，保留其他工具契约。"""
    if isinstance(value, list):
        return [normalize_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: normalize_schema(item) for key, item in value.items() if key != "nullable"}
    return {"anyOf": [result, {"type": "null"}]} if value.get("nullable") else result


def load_tools():
    """从当前发布代码生成 15 个相同业务工具的参数声明。"""
    spec = yaml.safe_load((REPO / "bkflow/apigw/management/commands/data/api-resources.yml").read_text())
    tools = []
    for path, methods in spec["paths"].items():
        if "/harness/" not in path:
            continue
        operation = methods["post"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": operation["operationId"].removeprefix("harness_"),
                    "description": operation["description"],
                    "parameters": {
                        "type": "object",
                        "required": ["path_param", "body_param"],
                        "additionalProperties": False,
                        "properties": {
                            "path_param": {
                                "type": "object",
                                "required": ["space_id"],
                                "additionalProperties": False,
                                "properties": {"space_id": {"type": "string"}},
                            },
                            "body_param": normalize_schema(schema),
                        },
                    },
                },
            }
        )
    assert len(tools) == 15
    return tools


TOOLS = load_tools()
GET_SCHEMA = next(tool["function"]["parameters"] for tool in TOOLS if tool["function"]["name"] == "get_debug_session")


def error_response(path, code="SCHEMA_VALIDATION_ERROR", request_schema=False):
    """回放业务错误，不向模型回显外部异常。"""
    action = "repair_tool_arguments" if request_schema else "repair_a2flow"
    return {
        "ok": False,
        "artifact_refs": [],
        "errors": [
            {
                "category": "VALIDATION",
                "code": code,
                "path": path,
                "repairable": True,
                "retryable": False,
                "message": (
                    "The tool arguments do not match the request schema."
                    if request_schema
                    else "The workflow input does not match its schema."
                ),
                "suggested_action": action,
            }
        ],
        "next_actions": [action],
    }


def build_page(body):
    """用已捕获节点重现数量和 8 KiB 预算，保留真实游标。"""
    offset = 0
    if body.get("node_cursor"):
        try:
            value = body["node_cursor"]
            owner, digest, offset = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
            if owner != SESSION or digest != SNAPSHOT or not isinstance(offset, int) or not 0 <= offset < len(NODES):
                raise ValueError()
        except (ValueError, TypeError):
            return None, "node_cursor"
    nodes = NODES
    if body.get("node_id"):
        if body.get("node_cursor"):
            return None, "node_id"
        nodes = [node for node in nodes if node["node_id"] == body["node_id"]]
        if not nodes:
            return None, "node_id"
    page = copy.deepcopy(FIXTURE["pages"][0])
    page.update(
        items=[], next_cursor=None, coverage={"offset": offset, "returned": 0, "total": len(nodes), "has_more": False}
    )
    for index in range(offset, min(len(nodes), offset + body.get("node_limit", 10))):
        cursor = encode([SESSION, SNAPSHOT, index + 1]) if index + 1 < len(nodes) else None
        candidate = {
            **page,
            "items": page["items"] + [nodes[index]],
            "next_cursor": cursor,
            "coverage": {
                "offset": offset,
                "returned": len(page["items"]) + 1,
                "total": len(nodes),
                "has_more": cursor is not None,
            },
        }
        if len(dump(candidate).encode()) > 8192 - 256:
            break
        page = candidate
    return page, None


def replay(name, arguments, variant, seen_history):
    """只返回固定合成快照，拒绝所有写工具和跨空间请求。"""
    if name != "get_debug_session":
        return error_response("tool", "LOCAL_READ_ONLY_POLICY"), seen_history
    try:
        jsonschema.validate(arguments, GET_SCHEMA)
    except jsonschema.ValidationError:
        return error_response("request", request_schema=True), seen_history
    body = arguments["body_param"]
    if arguments["path_param"]["space_id"] != SPACE_ID or body["session_id"] != SESSION:
        return error_response("scope", "LOCAL_READ_ONLY_POLICY"), seen_history
    page, error = build_page(body)
    if error:
        return error_response(error), seen_history
    events = copy.deepcopy(FIXTURE["base_artifact"]["history"]["items"])
    if body.get("cursor"):
        cursors = {encode([event["occurred_at"], event["event_id"]]): index + 1 for index, event in enumerate(events)}
        if body["cursor"] not in cursors:
            return error_response("cursor"), seen_history
        events = events[cursors[body["cursor"]] :]
    history_items = events[: body.get("limit", 20)]
    history_cursor = (
        encode([history_items[-1]["occurred_at"], history_items[-1]["event_id"]])
        if len(history_items) < len(events)
        else None
    )
    artifact = copy.deepcopy(FIXTURE["base_artifact"])
    artifact["context_page"] = page
    artifact["history"] = {"items": history_items, "next_cursor": history_cursor}
    artifact["read_guidance"].update(
        node_query="single_node" if body.get("node_id") else "all_nodes",
        node_page_has_more=page["coverage"]["has_more"],
        history_has_more=history_cursor is not None,
    )
    if variant == "compact":
        repeated = len([event for event in history_items if event["event_id"] in seen_history])
        artifact["history"]["items"] = [event for event in history_items if event["event_id"] not in seen_history]
        artifact["history"]["already_returned_items"] = repeated
        artifact["history"]["total_events"] = len(FIXTURE["base_artifact"]["history"]["items"])
        allowed = {
            "name",
            "node_id",
            "source_node_id",
            "node_type",
            "status",
            "outputs",
            "missing_vars",
            "last_execution_mode",
            "configured_execution_mode",
            "log_ref",
            "error_detail",
        }
        page["items"] = [{key: value for key, value in node.items() if key in allowed} for node in page["items"]]
        page["metadata"] = {
            key: page["metadata"][key]
            for key in (
                "global_vars",
                "template_id",
                "last_task_id",
                "last_run_type",
                "last_run_status",
                "last_error_detail",
            )
        }
        artifact.pop("reset_impact", None)
    seen_history = seen_history | {event["event_id"] for event in history_items}
    response = copy.deepcopy(FIXTURE["envelope"])
    response.update(
        artifact_refs=[artifact],
        correlation_id="local-replay-only",
        next_actions=["get_debug_session"] if page["coverage"]["has_more"] or history_cursor else [],
    )
    return response, seen_history


def self_test():
    """先证明回放与真实捕获页一致，并验证只读边界。"""
    cursor = None
    history_seen = set()
    for expected in FIXTURE["pages"]:
        body = {"session_id": SESSION, "node_limit": 3, "limit": 100}
        if cursor:
            body["node_cursor"] = cursor
        arguments = {"path_param": {"space_id": SPACE_ID}, "body_param": body}
        full, _ = replay("get_debug_session", arguments, "full", set())
        compact, history_seen = replay("get_debug_session", arguments, "compact", history_seen)
        full_page = full["artifact_refs"][0]["context_page"]
        compact_page = compact["artifact_refs"][0]["context_page"]
        assert full_page == expected
        for field in ("coverage", "next_cursor", "snapshot_id", "verification"):
            assert full_page[field] == compact_page[field]
        for left, right in zip(full_page["items"], compact_page["items"]):
            assert all(left[key] == right[key] for key in right)
        cursor = expected["next_cursor"]
    assert len(history_seen) == 15
    args = {"path_param": {"space_id": SPACE_ID}, "body_param": {"session_id": SESSION, "node_limit": 10}}
    assert (
        replay("get_debug_session", args, "full", set())[0]["artifact_refs"][0]["context_page"]["coverage"]["returned"]
        == 9
    )
    assert not replay("run_debug", args, "full", set())[0]["ok"]
    args["path_param"]["space_id"] = SPACE_ID + "-forbidden"
    assert not replay("get_debug_session", args, "full", set())[0]["ok"]
    args["path_param"]["space_id"] = SPACE_ID
    args["body_param"]["node_cursor"] = FIXTURE["pages"][0]["next_cursor"] + "=="
    assert not replay("get_debug_session", args, "full", set())[0]["ok"]
    print(
        json.dumps({"self_test": "passed", "tools": len(TOOLS), "pages_equal_to_capture": 4, "nodes": len(NODES)}),
        flush=True,
    )


def run(variant, output, model=MODEL):
    """保留所有历史、不自动压缩，最多六次工具调用；不强制模型输出总结。"""
    from urllib.parse import urlsplit

    endpoint = urlsplit(ENDPOINT)
    if endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Only a loopback HTTP model endpoint is supported")
    if endpoint.username or endpoint.password:
        raise ValueError("Credentials must not appear in the endpoint URL")
    token = os.environ.get("HARNESS_REPLAY_API_KEY", "")
    messages = [
        {"role": "system", "content": FIXTURE["system_prompt"]},
        {"role": "user", "content": FIXTURE["user_prompt"]},
    ]
    result = {
        "variant": variant,
        "requested_model": model,
        "endpoint": ENDPOINT,
        "prompt_sha256": hashlib.sha256(dump(messages).encode()).hexdigest(),
        "tool_count": len(TOOLS),
        "tool_schema_sha256": hashlib.sha256(dump(TOOLS).encode()).hexdigest(),
        "started_at": time.time(),
        "temperature": 0,
        "max_tokens": 8192,
        "rounds": [],
        "calls": [],
        "final": None,
    }

    class RejectRedirect(urllib.request.HTTPRedirectHandler):
        """禁止把本机模型凭证通过重定向转发到其他地址。"""

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirect())
    seen_history = set()
    try:
        for turn in range(8):
            payload = {
                "model": model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0,
                "max_tokens": 8192,
                "stream": False,
            }
            request = urllib.request.Request(
                ENDPOINT,
                data=dump(payload).encode(),
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                method="POST",
            )
            started = time.time()
            with opener.open(request, timeout=180) as response:
                data = json.load(response)
            choice = data["choices"][0]
            message = choice["message"]
            calls = message.get("tool_calls") or []
            round_info = {
                "turn": turn + 1,
                "model": data.get("model"),
                "response_id": data.get("id"),
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage"),
                "seconds": round(time.time() - started, 2),
                "tool_calls": len(calls),
            }
            result["rounds"].append(round_info)
            print(dump({"variant": variant, **round_info}), flush=True)
            messages.append(
                {
                    key: value
                    for key, value in message.items()
                    if key in ("role", "content", "tool_calls", "reasoning_content")
                }
            )
            if not calls:
                result["final"] = message.get("content")
                result["stop_reason"] = choice.get("finish_reason")
                break
            for call in calls:
                if len(result["calls"]) >= 6:
                    result["stop_reason"] = "tool_budget_exceeded"
                    return
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    replayed, seen_history = replay(name, arguments, variant, seen_history)
                except (ValueError, TypeError):
                    arguments = {"invalid_json": True}
                    replayed = error_response("request", request_schema=True)
                entry = {
                    "name": name,
                    "arguments": arguments,
                    "response": replayed,
                    "response_chars": len(dump(replayed)),
                }
                result["calls"].append(entry)
                print(
                    dump(
                        {
                            "variant": variant,
                            "call": len(result["calls"]),
                            "tool": name,
                            "ok": replayed["ok"],
                            "coverage": (
                                replayed.get("artifact_refs", [{}])[0].get("context_page", {}).get("coverage")
                                if replayed.get("artifact_refs")
                                else None
                            ),
                        }
                    ),
                    flush=True,
                )
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": dump(replayed)})
        else:
            result["stop_reason"] = "round_budget_exceeded"
    except Exception as exc:
        result["stop_reason"] = "transport_error"
        result["error_type"] = type(exc).__name__
        if isinstance(exc, urllib.error.HTTPError):
            result["http_status"] = exc.code
        print(
            dump({"variant": variant, "error_type": result["error_type"], "status": result.get("http_status")}),
            flush=True,
        )
    finally:
        result["ended_at"] = time.time()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--space-id", required=True)
    parser.add_argument("--variant", choices=("full", "compact"))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    load_fixture(options.fixture, options.space_id)
    self_test()
    if options.variant:
        if not options.output or options.output.exists():
            parser.error("A fresh output path is required")
        run(options.variant, options.output, options.model)
