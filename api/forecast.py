import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from starlette.applications import Starlette
from starlette.routing import Route
from server import get_forecast

routes = [
    Route("/api/forecast", endpoint=get_forecast, methods=["GET"]),
    Route("/", endpoint=get_forecast, methods=["GET"])
]
app = Starlette(routes=routes)
