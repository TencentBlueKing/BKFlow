"""Isolated synthetic API for exercising real BKFlow HTTP components.

No BKFlow imports, databases, credentials, outbound requests or business writes.
The local entrypoint listens on loopback only. Cloud hosting must supply network
isolation, authentication, rate limits and a production WSGI server separately.
"""

import argparse
import json
import re
from http import HTTPStatus
from urllib.parse import parse_qs
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

MAX_BODY = 4096
CHECK_FIELDS = {"check_id", "service", "scenario"}
REPORT_FIELDS = {"check_id", "service", "status", "latency_ms", "source_request_id"}
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
REQUEST_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")


def valid_identity(data):
    """Only synthetic service names and bounded non-secret test IDs are accepted."""
    return (
        isinstance(data.get("check_id"), str)
        and IDENTIFIER.fullmatch(data["check_id"]) is not None
        and data.get("service") in ("alpha", "beta")
    )


def error(status, code):
    return status, {"ok": False, "synthetic": True, "error": code}


def route(environ):
    """Validate requests before computing or echoing any values."""
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET")
    query = environ.get("QUERY_STRING", "")
    expected_methods = {"/healthz": "GET", "/v1/checks": "GET", "/v1/reports": "POST"}
    if path not in expected_methods:
        return error(404, "NOT_FOUND")
    if method != expected_methods[path]:
        return error(405, "METHOD_NOT_ALLOWED")
    if len(query) > 512 or (path != "/v1/checks" and query):
        return error(400, "INVALID_QUERY")
    if path == "/healthz":
        return 200, {"ok": True, "synthetic": True, "service": "a2flow-real-node-fixture"}

    if path == "/v1/checks":
        try:
            fields = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
        except ValueError:
            return error(400, "INVALID_CHECK_PARAMETERS")
        if set(fields) != CHECK_FIELDS or any(len(values) != 1 for values in fields.values()):
            return error(400, "INVALID_CHECK_PARAMETERS")
        data = {key: values[0] for key, values in fields.items()}
        if not valid_identity(data) or data["scenario"] not in ("healthy", "degraded"):
            return error(400, "INVALID_CHECK_PARAMETERS")
        return 200, {
            "ok": True,
            "synthetic": True,
            "request_id": str(uuid4()),
            "check_id": data["check_id"],
            "service": data["service"],
            "status": data["scenario"],
            "latency_ms": 12 if data["scenario"] == "healthy" else 850,
            "received": data,
        }

    if environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower() != "application/json":
        return error(415, "JSON_REQUIRED")
    if environ.get("HTTP_TRANSFER_ENCODING"):
        return error(400, "CONTENT_LENGTH_REQUIRED")
    try:
        size = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        return error(400, "INVALID_CONTENT_LENGTH")
    if size > MAX_BODY:
        return error(413, "BODY_TOO_LARGE")
    if size <= 0:
        return error(400, "INVALID_JSON")
    try:
        data = json.loads(environ["wsgi.input"].read(size))
    except (ValueError, UnicodeDecodeError):
        return error(400, "INVALID_JSON")
    if (
        not isinstance(data, dict)
        or set(data) != REPORT_FIELDS
        or not valid_identity(data)
        or data["status"] not in ("healthy", "degraded")
        or type(data["latency_ms"]) is not int
        or not 0 <= data["latency_ms"] <= 10000
        or not isinstance(data["source_request_id"], str)
        or REQUEST_ID.fullmatch(data["source_request_id"]) is None
    ):
        return error(400, "INVALID_REPORT_PARAMETERS")
    return 200, {
        "ok": True,
        "synthetic": True,
        "request_id": str(uuid4()),
        "source_request_id": data["source_request_id"],
        "summary": "{check_id} | {service} | {status} | {latency_ms} ms".format(**data),
        "received": data,
    }


def application(environ, start_response):
    """WSGI entrypoint; responses and receipts never include arbitrary headers."""
    status, data = route(environ)
    body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    start_response(
        "{} {}".format(status, HTTPStatus(status).phrase),
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    if data.get("request_id"):
        # Only validated synthetic fields; no raw path, headers, body or tokens.
        print(
            json.dumps(
                {
                    "event": "fixture_request",
                    "endpoint": environ["PATH_INFO"],
                    "request_id": data["request_id"],
                    "received": data["received"],
                }
            ),
            flush=True,
        )
    return [body]


class LocalRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Avoid the default access log echoing unvalidated paths or query strings.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    with make_server("127.0.0.1", args.port, application, handler_class=LocalRequestHandler) as server:
        print("Fixture listening on http://127.0.0.1:{} (local only)".format(server.server_port), flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
