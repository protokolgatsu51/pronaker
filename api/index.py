import os
import sys

# Ensure repository root is on sys.path so app and its local modules can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# WSGI middleware to normalize PATH_INFO from Vercel proxy headers
class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get("QUERY_STRING", "").strip() == "debug_env=1":
            import json
            start_response("200 OK", [("Content-Type", "application/json")])
            data = {k: str(v) for k, v in environ.items() if isinstance(v, (str, int, float, bool))}
            return [json.dumps(data, indent=2).encode("utf-8")]

        # Check for original URL passed by Vercel Edge
        orig_path = (
            environ.get("HTTP_X_FORWARDED_URI") or
            environ.get("HTTP_X_MATCHED_PATH") or
            environ.get("HTTP_X_NOW_ROUTE_MATCHES")
        )
        if orig_path:
            # Strip query string if any
            if "?" in orig_path:
                orig_path = orig_path.split("?")[0]
            environ["PATH_INFO"] = orig_path
        else:
            path = environ.get("PATH_INFO", "")
            if path in ("/api/index.py", "/api/index", "/api"):
                environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
