from http.server import BaseHTTPRequestHandler
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import WELLS_DATA, get_wells
from starlette.applications import Starlette
from starlette.routing import Route


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        response = {"wells": WELLS_DATA}
        self.wfile.write(json.dumps(response).encode("utf-8"))


routes = [
    Route("/api/wells", endpoint=get_wells, methods=["GET"]),
    Route("/", endpoint=get_wells, methods=["GET"])
]
app = Starlette(routes=routes)
