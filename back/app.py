# back/app.py
import os, re
from starlette.responses import JSONResponse

# token must match what you put in Render env BACKEND_API_TOKEN
API_TOKEN = os.getenv("BACKEND_API_TOKEN", "")

# match your allowed origins (same list as main.py)
_ALLOWED = [
    o.strip() for o in os.getenv(
        "ALLOW_ORIGINS",
        "https://engie-news-repo3-0.vercel.app,http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
]
_VERCL_RE = re.compile(r"^https://[a-z0-9-]+\.vercel\.app$", re.I)

def _origin_ok(origin: str) -> bool:
    return bool(origin) and (origin in _ALLOWED or _VERCL_RE.match(origin))

def attach_cors_headers(origin: str, headers: dict):
    if _origin_ok(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
        headers["Access-Control-Allow-Credentials"] = "false"

def init_guard_middleware(app):
    @app.middleware("http")
    async def guard_refresh(request, call_next):
        # Let OPTIONS continue (handled by your CORS code in main.py)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in ("/refresh", "/refresh/events"):
            auth = request.headers.get("authorization", "")
            ok = API_TOKEN and auth == f"Bearer {API_TOKEN}"
            if not ok:
                # return 401 but *with* CORS headers so browser doesn't complain
                headers = {}
                attach_cors_headers(request.headers.get("origin", ""), headers)
                return JSONResponse({"error": "Unauthorized"}, status_code=401, headers=headers)

        return await call_next(request)
