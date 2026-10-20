"""Webhook 正式包跨版本投递探针，仅允许连接本地隔离服务。"""

import argparse
import copy
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

QUEUE = "lts_webhook_upgrade"
ENDPOINT = "http://127.0.0.1:19998"
TOKEN = "local-upgrade-token"
PASSWORD = "local-upgrade-password"
HEADER = "local-upgrade-header"


def serve(path):
    """记录真实 HTTP 请求；retry 路径第一次失败，后续成功。"""
    attempts = {}

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            delivery_id = body["delivery_id"]
            attempts[delivery_id] = attempts.get(delivery_id, 0) + 1
            status = 503 if "/retry/" in self.path and attempts[delivery_id] == 1 else 200
            record = {
                "delivery_id": delivery_id,
                "body": body,
                "authorization": self.headers.get("Authorization"),
                "header": self.headers.get("X-Upgrade-Test"),
                "status": status,
            }
            with path.open("a") as output:
                output.write(json.dumps(record) + "\n")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"accepted": status == 200}).encode())

        def log_message(self, *_args):
            pass

    ThreadingHTTPServer(("127.0.0.1", 19998), Receiver).serve_forever()


def setup():
    """在 AppConfig 初始化前检查所有外部连接。"""
    import django
    from django.conf import settings

    db = settings.DATABASES["default"]
    assert (db["HOST"], str(db["PORT"]), db["NAME"]) == ("127.0.0.1", "13306", "bkflow_lts_interface")
    broker = urlparse(settings.BROKER_URL)
    assert (broker.hostname, broker.port) == ("127.0.0.1", 15673)
    assert settings.REDIS["host"] == "127.0.0.1" and int(settings.REDIS["port"]) == 16379
    assert settings.BKFLOW_MODULE.code == "lts"
    django.setup()


def seed(path, retry_only=False):
    """使用 BKFlow 配置入口和包的信号入口生成加密配置与队列消息。"""
    from celery import current_app
    from webhook.handlers import Webhooker
    from webhook.models import Event, History, Webhook
    from webhook.signals import event_broadcast_signal

    from bkflow.constants import WebhookEventType
    from bkflow.utils.webhook import apply_webhook_configs

    current_app.conf.task_routes = {Webhooker.send_webhook_task.name: {"queue": QUEUE}}
    event_code = WebhookEventType.TASK_FINISHED.value
    Event.objects.get_or_create(code=event_code, defaults={"name": "local upgrade task finished"})
    cases = {}
    for kind in ["retry"] if retry_only else ["bearer", "basic", "retry"]:
        scope = "{}-{}".format(path.stem, kind)
        delivery_id = "delivery-" + scope
        assert not History.objects.filter(delivery_id=delivery_id).exists()
        config = {
            "method": "POST",
            "endpoint": "{}/{}/{}".format(ENDPOINT, kind, scope),
            "extra_info": {
                "headers": [{"key": "X-Upgrade-Test", "value": HEADER}],
                "authorization": {
                    "type": "basic" if kind == "basic" else "bearer",
                    "username": "fixture",
                    "password": PASSWORD,
                    "token": TOKEN,
                },
                "data": {"fixture": scope},
                "timeout": 5,
                "retry_times": 2,
                "interval": 20 if retry_only else 1,
            },
        }
        result = apply_webhook_configs(copy.deepcopy(config), scope)
        assert result["result"], result
        stored = Webhook.objects.get(code="template_{}_webhook".format(scope))
        assert stored.extra_info["headers"][0]["value"] != HEADER
        assert stored.extra_info["authorization"]["token"] != TOKEN
        event_broadcast_signal.send(
            sender=event_code,
            scopes=[("template", scope)],
            extra_info={"delivery_id": delivery_id, "fixture_event": scope},
        )
        cases[kind] = {"scope": scope, "delivery_id": delivery_id, "config": config}
    path.write_text(json.dumps({"cases": cases, "task_name": Webhooker.send_webhook_task.name}, indent=2))
    print("WEBHOOK_SEEDED", path.name, len(cases))


def verify(path, phase):
    """校验历史、解密、回显与更新；不以 worker 日志替代结果。"""
    from webhook.models import History

    from bkflow.utils.webhook import apply_webhook_configs, get_webhook_configs

    manifest = json.loads(path.read_text())
    deadline = time.monotonic() + 70
    while True:
        rows = {
            kind: list(
                History.objects.filter(delivery_id=case["delivery_id"])
                .order_by("id")
                .values("success", "status_code", "extra_info")
            )
            for kind, case in manifest["cases"].items()
        }
        if phase == "failed":
            if rows["retry"]:
                assert [r["status_code"] for r in rows["retry"]] == [503], rows
                print("WEBHOOK_RETRY_PENDING", path.name)
                return
        elif all(
            [r["status_code"] for r in records] == ([503, 200] if kind == "retry" else [200])
            for kind, records in rows.items()
        ):
            break
        assert time.monotonic() < deadline, rows
        time.sleep(0.2)
    for kind, case in manifest["cases"].items():
        assert rows[kind][-1]["success"] is True
        assert rows[kind][-1]["extra_info"]["request"]["json"]["delivery_id"] == case["delivery_id"]
        config = get_webhook_configs(case["scope"])
        assert config["extra_info"]["headers"][0]["value"] == HEADER
        assert config["extra_info"]["authorization"]["password"] == PASSWORD
        assert config["extra_info"]["authorization"]["token"] == TOKEN
        if phase == "verify":
            config["extra_info"]["data"]["updated_by_consumer"] = True
            result = apply_webhook_configs(config, case["scope"])
            assert result["result"], result
        elif phase == "read_updated":
            assert config["extra_info"]["data"]["updated_by_consumer"] is True
    summary = {kind: [r["status_code"] for r in records] for kind, records in rows.items()}
    if phase == "verify":
        path.with_suffix(".result.json").write_text(json.dumps({"passed": True, "statuses": summary}, indent=2))
    print("WEBHOOK_VERIFIED", phase, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["serve", "seed", "seed_retry", "failed", "verify", "read_updated"])
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.phase == "serve":
        serve(args.manifest)
    else:
        setup()
        if args.phase in ("seed", "seed_retry"):
            seed(args.manifest, retry_only=args.phase == "seed_retry")
        else:
            verify(args.manifest, args.phase)
