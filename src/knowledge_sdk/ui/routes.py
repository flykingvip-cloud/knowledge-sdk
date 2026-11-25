"""Static shell and an explicitly opt-in, loopback-only development signer.

Never enable the signer against real data. Production uses the existing HMAC
host gateway; neither a shared secret nor an unsigned Actor enters the browser.
"""
from __future__ import annotations
import knowledge_sdk
import re
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ..client.http_client import OPERATIONS
from ..contracts.models import Actor
from ..exceptions import ValidationError
from ..server.auth import signed_headers

STATIC = Path(__file__).with_name("static")
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def normalize_ui_prefix(prefix):
    # Deliberately reject encoded separators, query/fragment and empty segments.
    if (not isinstance(prefix, str) or not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+/?", prefix)
        or prefix.rstrip("/") in ("/v1", "/docs", "/redoc") or prefix.startswith("/v1/")):
        raise ValidationError("UI prefix must be a non-root absolute path outside /v1")
    return prefix.rstrip("/")


def route_path(request):
    path, root = request.scope["path"], request.scope.get("root_path", "").rstrip("/")
    if root and (path == root or path.startswith(root + "/")):
        return path[len(root):] or "/"
    return path


def public_ui_path(path, prefix):
    return path in (prefix, prefix + "/", prefix + "/config", prefix + "/demo/sign") or path.startswith(prefix + "/assets/")


def mount_workbench(app, client, auth_secret, enable_demo_switcher, ui_prefix="/ui"):
    ui_prefix = normalize_ui_prefix(ui_prefix)
    @app.middleware("http")
    async def ui_security_headers(request, call_next):
        path = route_path(request)  # mounts may mutate scope.root_path downstream
        response = await call_next(request)
        if public_ui_path(path, ui_prefix):
            response.headers.update({
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'",
                "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store"})
        # Authenticated responses must not be cached across identity switches.
        if path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get(ui_prefix, include_in_schema=False)
    @app.get(ui_prefix + "/", include_in_schema=False)
    async def index(request: Request):
        root = request.scope.get("root_path", "").rstrip("/")
        if root:
            normalize_ui_prefix(root)  # configured ASGI root only; never forwarded headers
        prefix = root + ui_prefix
        enterprise=getattr(app.state,'auth_mode','hmac') in ('oidc','dual')
        html = (STATIC / ("enterprise.html" if enterprise else "index.html")).read_text(encoding="utf-8")
        html = html.replace('href="/ui', 'href="' + prefix).replace('src="/ui', 'src="' + prefix)
        if not enable_demo_switcher:
            # Disable simulation on the initial response too (before JS/config).
            html = re.sub(r'(<form id="identity-form"[^>]*>)(.*?)(</form>)',
                          lambda m: m[1] + re.sub(r'<(input|select|button)\b', r'<\1 disabled=""', m[2]) + m[3],
                          html, flags=re.DOTALL)
        return HTMLResponse(html)

    @app.get(ui_prefix + "/config", include_in_schema=False)
    async def config(request: Request):
        root = request.scope.get("root_path", "").rstrip("/")
        if root: normalize_ui_prefix(root)
        raw = request.scope.get("raw_path", request.scope["path"].encode()).decode("ascii")
        suffix = ui_prefix + "/config"
        signature_base = raw[:-len(suffix)] if raw.endswith(suffix) else ""
        return {"demo_enabled": bool(enable_demo_switcher), "operations": OPERATIONS,
                "vector_available": getattr(client, "vector_index", None) is not None,
                "auth": "oidc-session" if getattr(app.state,"auth_mode","hmac") in ("oidc","dual") else "hmac-gateway", "version": knowledge_sdk.__version__,
                "ui_base": root + ui_prefix, "api_base": root, "signature_base": signature_base}

    if enable_demo_switcher:
        @app.post(ui_prefix + "/demo/sign", include_in_schema=False)
        async def sign(request: Request):
            # All checks are independent of reverse-proxy / forwarded headers.
            # Origin + non-simple header prevents CSRF; Host blocks DNS rebinding.
            if (not request.client or request.client.host not in LOOPBACK
                or request.url.hostname not in LOOPBACK
                or request.headers.get("origin") != str(request.url).split("/", 3)[0] + "//" + str(request.url).split("/", 3)[2]
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
                raw_sign = request.scope.get("raw_path", request.scope["path"].encode()).decode("ascii")
                suffix = ui_prefix + "/demo/sign"
                signature_base = raw_sign[:-len(suffix)] if raw_sign.endswith(suffix) else ""
                allowed = {(verb, signature_base + p) for verb, p in OPERATIONS.values()}
                if (path.scheme or path.netloc or path.fragment
                    or (method, path.path) not in allowed
                    or (method == "GET" and payload)):
                    raise ValueError()
                headers = signed_headers(actor, auth_secret, method, target, payload.encode("utf-8"))
                return {"headers": headers}
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise ValidationError("Invalid demo signing request") from exc

    app.mount(ui_prefix + "/assets", StaticFiles(directory=str(STATIC)), name="workbench-assets")
