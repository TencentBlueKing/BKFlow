"""Loopback-only interface responses for the worker upgrade rehearsal.

Run this with the path to the current periodic_seed manifest when testing beat.
It supplies template data, space variables and event acknowledgements only.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def respond(self):
        path = self.path.split("?")[0]
        if self.command == "POST":
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if path in ("/api/space/internal/broadcast_task_events/", "/api/variable/internal/get_variable/"):
            result = {}
        elif path == "/api/template/internal/987654/get_template_data/" and len(sys.argv) == 2:
            result = {"pipeline_tree": json.loads(Path(sys.argv[1]).read_text())["pipeline_tree"]}
        else:
            self.send_error(404)
            return
        data = json.dumps({"result": True, "data": result, "message": ""}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = respond
    do_POST = respond


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 19999), Handler).serve_forever()
