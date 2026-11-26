import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from starlette.applications import Starlette
from starlette.routing import Route
from server import post_guard_validate

routes = [
    Route("/api/guard/validate", endpoint=post_guard_validate, methods=["POST"]),
    Route("/", endpoint=post_guard_validate, methods=["POST"])
]
app = Starlette(routes=routes)
