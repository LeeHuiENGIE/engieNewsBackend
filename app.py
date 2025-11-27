# app.py
import os
from starlette.responses import Response
from back.main import app as _app  # reuse your FastAPI app & routes

BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN", "").strip()

@_app.middleware("http")
async def guard_refresh(request, call_next):
    # Always allow preflight so the browser can proceed to the real POST
    if request.method.upper() == "OPTIONS":
        # Return 200 with minimal headers (CORS headers are added by your CORS middleware)
        return Response(status_code=200)

    path = request.url.path

    # Only protect actual POST refresh endpoints
    if request.method.upper() == "POST" and path.startswith("/refresh"):
        if BACKEND_API_TOKEN and request.headers.get("x-backend-token") != BACKEND_API_TOKEN:
            # Include CORS-friendly headers so the browser can read the 401
            return Response(status_code=401, content="Unauthorized")

    return await call_next(request)

# Uvicorn entrypoint expects "app"
app = _app