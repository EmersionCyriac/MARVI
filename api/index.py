import os
import sys

# Ensure root directory is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from server import app as starlette_app


async def app(scope, receive, send):
    """ASGI entrypoint for Vercel Serverless Functions with path normalization."""
    if scope.get("type") == "http":
        path = scope.get("path", "/")

        # 1. Normalize Vercel internal script rewrites to root / clean API paths
        if path in (
            "/api/index.py",
            "/api/index",
            "/api/index.py/",
            "/api/index/",
            "/api",
            "/api/",
        ):
            scope["path"] = "/"
        elif path.startswith("/api/index.py/"):
            scope["path"] = path[len("/api/index.py") :]
        elif path.startswith("/api/index/"):
            scope["path"] = path[len("/api/index") :]

        # 2. Check headers for original requested path forwarded by Vercel edge proxy
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
