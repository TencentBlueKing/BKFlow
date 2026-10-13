"""Offline and loopback-only checks; no model provider or BKFlow is contacted."""

import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch


class ReplayTests(unittest.TestCase):
    """Exercise the exported replay script with entirely synthetic inputs."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("harness_replay", Path(__file__).with_name("replay.py"))
        self.replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.replay)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "result.json"
        self.session = "00000000-0000-4000-8000-000000000001"
        fixture = {
            "system_prompt": "Read the synthetic snapshot only.",
            "user_prompt": "Summarize the two nodes.",
            "envelope": {"ok": True},
            "base_artifact": {
                "session": {"session_id": self.session},
                "history": {"items": []},
                "read_guidance": {},
            },
            "pages": [
                {
                    "snapshot_id": "a" * 64,
                    "items": [
                        {"node_id": "A", "outputs": {"result": "synthetic-A"}},
                        {"node_id": "B", "outputs": {"result": "synthetic-B"}},
                    ],
                }
            ],
        }
        path = Path(self.temp.name) / "fixture.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        self.replay.load_fixture(path, "1")
        self.arguments = {"path_param": {"space_id": "1"}, "body_param": {"session_id": self.session}}

    def test_only_matching_read_tool_is_allowed(self):
        """Write tools and foreign scopes must fail before any real service call."""
        response, _ = self.replay.replay("run_debug", self.arguments, "full", set())
        self.assertEqual(response["errors"][0]["code"], "LOCAL_READ_ONLY_POLICY")
        self.arguments["path_param"]["space_id"] = "2"
        response, _ = self.replay.replay("get_debug_session", self.arguments, "full", set())
        self.assertEqual(response["errors"][0]["code"], "LOCAL_READ_ONLY_POLICY")

    def test_pagination_preserves_each_node_and_finishes(self):
        """A cursor must resume after A, return B, and advertise no further read."""
        self.arguments["body_param"]["node_limit"] = 1
        first, _ = self.replay.replay("get_debug_session", self.arguments, "full", set())
        page = first["artifact_refs"][0]["context_page"]
        self.assertEqual(page["items"], [{"node_id": "A", "outputs": {"result": "synthetic-A"}}])
        self.assertTrue(page["coverage"]["has_more"])
        self.arguments["body_param"]["node_cursor"] = page["next_cursor"]
        last, _ = self.replay.replay("get_debug_session", self.arguments, "full", set())
        page = last["artifact_refs"][0]["context_page"]
        self.assertEqual(page["items"], [{"node_id": "B", "outputs": {"result": "synthetic-B"}}])
        self.assertFalse(page["coverage"]["has_more"])
        self.assertEqual(last["next_actions"], [])

    def test_external_model_endpoint_is_rejected(self):
        """Endpoint overrides cannot send captured evidence to a remote host directly."""
        for endpoint in ("https://example.invalid/v1", "http://example.invalid/v1", "http://user:pass@localhost/v1"):
            with self.subTest(endpoint=endpoint):
                self.replay.ENDPOINT = endpoint
                with self.assertRaises(ValueError):
                    self.replay.run("full", self.output)
        self.assertFalse(self.output.exists())

    def local_model(self, *, redirect=False):
        """Serve a bounded synthetic response and record only request paths."""
        paths = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                paths.append(self.path)
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(302 if redirect else 200)
                if redirect:
                    self.send_header("Location", "/must-not-follow")
                self.end_headers()
                if not redirect:
                    self.wfile.write(
                        json.dumps(
                            {
                                "choices": [
                                    {
                                        "message": {"role": "assistant", "content": "synthetic result"},
                                        "finish_reason": "stop",
                                    }
                                ]
                            }
                        ).encode()
                    )

            def do_GET(self):
                paths.append(self.path)
                self.send_response(500)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(close)
        self.replay.ENDPOINT = "http://127.0.0.1:{}/v1/chat/completions".format(server.server_port)
        return paths

    def test_local_model_ignores_environment_proxy(self):
        """Only the configured local endpoint receives the synthetic request."""
        paths = self.local_model()
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "no_proxy": ""}):
            self.replay.run("full", self.output)
        result = json.loads(self.output.read_text())
        self.assertEqual(result["final"], "synthetic result")
        self.assertEqual(result["stop_reason"], "stop")
        self.assertEqual(paths, ["/v1/chat/completions"])

    def test_redirect_is_refused_without_persisting_credentials(self):
        """A redirect must stop before a second request and omit the test key from results."""
        paths = self.local_model(redirect=True)
        with patch.dict(os.environ, {"HARNESS_REPLAY_API_KEY": "synthetic-test-key"}):
            self.replay.run("full", self.output)
        raw = self.output.read_text()
        self.assertNotIn("synthetic-test-key", raw)
        self.assertEqual(json.loads(raw)["http_status"], 302)
        self.assertEqual(paths, ["/v1/chat/completions"])


if __name__ == "__main__":
    unittest.main()
