import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from starlette.applications import Starlette
from starlette.routing import Route
from server import post_advisory

routes = [
    Route("/api/advisory", endpoint=post_advisory, methods=["POST"]),
    Route("/", endpoint=post_advisory, methods=["POST"])
]
app = Starlette(routes=routes)
