import os
import sys
from urllib.parse import parse_qs

# Ensure root directory is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import app as starlette_app


async def app(scope, receive, send):
    """ASGI entrypoint for Vercel Serverless Functions with dynamic route resolution."""
    if scope.get("type") == "http":
        qs = scope.get("query_string", b"").decode("latin-1")
        parsed = parse_qs(qs)
        
        # 1. If Vercel rewrote via __route query param, extract it
        if "__route" in parsed and parsed["__route"]:
            subpath = parsed["__route"][0].lstrip("/")
            scope["path"] = f"/api/{subpath}"
            # Strip __route from query string so endpoints receive clean params
            clean_pairs = [p for p in qs.split("&") if not p.startswith("__route=")]
            scope["query_string"] = "&".join(clean_pairs).encode("latin-1")
        else:
            # 2. Check headers for original forwarded path
            for name, value in scope.get("headers", []):
                if name.lower() in (b"x-matched-path", b"x-invoke-path"):
                    try:
                        orig = value.decode("utf-8")
                        if orig and not orig.startswith("/api/index"):
                            scope["path"] = orig
                            break
                    except Exception:
                        pass

    await starlette_app(scope, receive, send)
