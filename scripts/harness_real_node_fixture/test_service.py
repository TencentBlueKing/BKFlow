"""Run with python3 -m unittest discover -s scripts/harness_real_node_fixture -v.

Tests use a real local HTTP server; they never read BKFlow settings or databases.
"""

import importlib.util
import json
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class FixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name("service.py")
        if not path.exists():
            return
        spec = importlib.util.spec_from_file_location("fixture_service", path)
        cls.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.service)
        cls.server = make_server("127.0.0.1", 0, cls.service.application, handler_class=QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://127.0.0.1:{}".format(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join(timeout=2)

    def request(self, path, payload=None, raw=None, headers=None):
        self.assertTrue(hasattr(self, "server"), "isolated fixture service is not implemented")
        body = json.dumps(payload).encode() if payload is not None else raw
        request = Request(self.base_url + path, data=body, headers=headers or {"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_health_is_explicitly_synthetic(self):
        status, data = self.request("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True, "synthetic": True, "service": "a2flow-real-node-fixture"})

    def test_check_parameters_change_the_real_response(self):
        status, data = self.request("/v1/checks?check_id=E2E-A&service=alpha&scenario=healthy")
        self.assertEqual(status, 200)
        self.assertEqual(data["check_id"], "E2E-A")
        self.assertEqual(data["service"], "alpha")
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["latency_ms"], 12)
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["received"], {"check_id": "E2E-A", "service": "alpha", "scenario": "healthy"})
        self.assertTrue(data["request_id"])
        status, other = self.request("/v1/checks?check_id=E2E-B&service=beta&scenario=degraded")
        self.assertEqual(status, 200)
        self.assertEqual(other["check_id"], "E2E-B")
        self.assertEqual(other["status"], "degraded")
        self.assertEqual(other["latency_ms"], 850)
        self.assertNotEqual(data["request_id"], other["request_id"])

    def test_report_uses_upstream_values_and_returns_receipt(self):
        _, check = self.request("/v1/checks?check_id=E2E-A&service=alpha&scenario=healthy")
        payload = {
            "check_id": check["check_id"],
            "service": check["service"],
            "status": check["status"],
            "latency_ms": check["latency_ms"],
            "source_request_id": check["request_id"],
        }
        status, report = self.request("/v1/reports", payload)
        self.assertEqual(status, 200)
        self.assertEqual(report["received"], payload)
        self.assertEqual(report["summary"], "E2E-A | alpha | healthy | 12 ms")
        self.assertEqual(report["source_request_id"], check["request_id"])
        self.assertTrue(report["synthetic"])
        self.assertTrue(report["request_id"])

    def test_rejects_missing_unknown_duplicate_or_unsafe_inputs(self):
        paths = [
            "/v1/checks",
            "/v1/checks?check_id=X&service=alpha&scenario=healthy&url=http://example.com",
            "/v1/checks?check_id=X&check_id=Y&service=alpha&scenario=healthy",
            "/v1/checks?check_id=X&service=production&scenario=healthy",
            "/v1/checks?check_id=X&service=alpha&scenario=healthy%0Asecret",
            "/v1/checks?check_id=" + "a" * 65 + "&service=alpha&scenario=healthy",
        ]
        for path in paths:
            with self.subTest(path=path):
                status, data = self.request(path)
                self.assertEqual(status, 400)
                self.assertFalse(data["ok"])
                self.assertNotIn("received", data)

    def test_rejects_bad_body_types_and_payloads(self):
        base = {
            "check_id": "E2E-A",
            "service": "alpha",
            "status": "healthy",
            "latency_ms": 12,
            "source_request_id": "26ac9cc9-89a9-4c6a-91fb-732e5b07e8da",
        }
        bad_payloads = [
            [],
            {},
            dict(base, latency_ms="12"),
            dict(base, latency_ms=True),
            dict(base, latency_ms=-1),
            dict(base, source_request_id="${unrendered}"),
            dict(base, token="not-a-real-secret"),
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                status, data = self.request("/v1/reports", payload)
                self.assertEqual(status, 400)
                self.assertFalse(data["ok"])
        self.assertEqual(self.request("/v1/reports", raw=b"not-json")[0], 400)
        self.assertEqual(self.request("/v1/reports", raw=b"x" * 4097)[0], 413)
        self.assertEqual(self.request("/v1/reports", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)

    def test_does_not_expose_paths_or_accept_write_operations(self):
        self.assertEqual(self.request("/v1/checks", {"anything": "ignored"})[0], 405)
        self.assertEqual(self.request("/v1/reports")[0], 405)
        self.assertEqual(self.request("/v1/reports?token=not-a-real-secret", {})[0], 400)
        self.assertEqual(self.request("/not-found")[0], 404)


if __name__ == "__main__":
    unittest.main()
