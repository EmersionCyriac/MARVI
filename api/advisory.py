from http.server import BaseHTTPRequestHandler
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from advisory.budget import WaterBudgetSimulator
from server import post_advisory
from starlette.applications import Starlette
from starlette.routing import Route

sim = WaterBudgetSimulator()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)
        try:
            body = json.loads(post_body.decode("utf-8"))
        except Exception:
            body = {}

        depth = float(body.get("depth_m", 10.0))
        diam = float(body.get("diameter_m", 2.5))
        total = float(body.get("total_depth_m", 18.0))
        area = float(body.get("area_ha", 1.0))

        advisory = sim.generate_advisory(
            current_depth_m=depth,
            well_diameter_m=diam,
            total_depth_m=total,
            farm_area_ha=area
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(advisory).encode("utf-8"))


routes = [
    Route("/api/advisory", endpoint=post_advisory, methods=["POST"]),
    Route("/", endpoint=post_advisory, methods=["POST"])
]
app = Starlette(routes=routes)
