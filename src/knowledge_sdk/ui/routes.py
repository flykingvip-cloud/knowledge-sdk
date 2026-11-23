from __future__ import annotations
"""Static shell and an explicitly opt-in, loopback-only development signer.

Never enable the signer against real data. Production uses the existing HMAC
host gateway; neither a shared secret nor an unsigned Actor enters the browser.
"""
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ..client.http_client import OPERATIONS
from ..contracts.models import Actor
from ..exceptions import ValidationError
from ..server.auth import signed_headers

STATIC = Path(__file__).with_name("static")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def mount_workbench(app, client, auth_secret, enable_demo_switcher):
    @app.middleware("http")
    async def ui_security_headers(request, call_next):
        response = await call_next(request)
        if request.url.path == "/ui" or request.url.path.startswith("/ui/"):
            response.headers.update({
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'",
                "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store"})
        # Authenticated responses must not be cached across identity switches.
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/ui", include_in_schema=False)
    @app.get("/ui/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/ui/config", include_in_schema=False)
    async def config():
        return {"demo_enabled": bool(enable_demo_switcher), "operations": OPERATIONS,
                "vector_available": getattr(client, "vector_index", None) is not None,
                "auth": "hmac-gateway", "version": "1.1.0"}

    if enable_demo_switcher:
        @app.post("/ui/demo/sign", include_in_schema=False)
        async def sign(request: Request):
            # All checks are independent of reverse-proxy / forwarded headers.
            # Origin + non-simple header prevents CSRF; Host blocks DNS rebinding.
            if (not request.client or request.client.host not in LOOPBACK
                or request.url.hostname not in LOOPBACK
                or request.headers.get("origin") != str(request.base_url).rstrip("/")
                or request.headers.get("x-kb-demo") != "1"
                or request.headers.get("sec-fetch-site", "same-origin") != "same-origin"):
                return JSONResponse(status_code=403, content={"message": "Demo signing is same-origin loopback only"})
            body = await request.body()
            if len(body) > 48 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"message": "Request too large"})
            try:
                import json
                data = json.loads(body)
                actor = Actor(**data["actor"])
                method, target, payload = data["method"], data["target"], data.get("body", "")
                if not isinstance(target, str) or not isinstance(payload, str): raise ValueError()
                path = urlsplit(target)
                if (path.scheme or path.netloc or path.fragment or not target.startswith("/v1/")
                    or (method, path.path) not in OPERATIONS.values()
                    or (method == "GET" and payload)):
                    raise ValueError()
                headers = signed_headers(actor, auth_secret, method, target, payload.encode("utf-8"))
                return {"headers": headers}
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise ValidationError("Invalid demo signing request") from exc

    app.mount("/ui/assets", StaticFiles(directory=str(STATIC)), name="workbench-assets")
