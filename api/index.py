import os
import sys
from urllib.parse import parse_qs

# Ensure repository root is on sys.path so app and its local modules can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# WSGI middleware to normalize PATH_INFO from Vercel rewrites
class VercelPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        if "path" in qs and qs["path"]:
            p = "/" + qs["path"][0].lstrip("/")
            environ["PATH_INFO"] = p
        else:
            orig = environ.get("HTTP_X_FORWARDED_URI") or environ.get("HTTP_X_MATCHED_PATH")
            if orig:
                environ["PATH_INFO"] = orig.split("?")[0]
            else:
                path = environ.get("PATH_INFO", "")
                if path in ("/api/index.py", "/api/index", "/api", ""):
                    environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
