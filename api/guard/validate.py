from http.server import BaseHTTPRequestHandler
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from data_guard.detector import SmartDataGuard
from server import post_guard_validate
from starlette.applications import Starlette
from starlette.routing import Route

guard = SmartDataGuard()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)
        try:
            body = json.loads(post_body.decode("utf-8"))
        except Exception:
            body = {}

        well_id = body.get("well_id", "RJ-DHT-01")
        depth = float(body.get("depth_m", 10.0))
        is_pumping = bool(body.get("is_pumping", False))

        result = guard.validate_reading(
            well_id=well_id,
            depth_m=depth,
            is_pumping=is_pumping
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))


routes = [
    Route("/api/guard/validate", endpoint=post_guard_validate, methods=["POST"]),
    Route("/", endpoint=post_guard_validate, methods=["POST"])
]
app = Starlette(routes=routes)
