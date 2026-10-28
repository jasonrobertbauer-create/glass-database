#!/usr/bin/env python3
"""
Serve the whole site locally the way the production proxy does — the static
pages at ``/`` (homepage, capture apps, Seasons, graph, map, shop) and the API
under ``/api/`` — so everything that isn't Streamlit can be developed and clicked
through without Apache. The Streamlit apps still run on their own ports
(``make run-glowtbook`` etc.); their links are redirected there.

    python -m scripts.dev_site            # http://127.0.0.1:8080/
    GLASSDB_DEV_LOGIN=1 python -m scripts.dev_site   # + a fake sign-in at /api/auth/dev-login
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEPLOY = ROOT / "deploy"

from starlette.applications import Starlette  # noqa: E402
from starlette.middleware import Middleware  # noqa: E402
from starlette.responses import FileResponse, PlainTextResponse, RedirectResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from api.main import app as api_app  # noqa: E402
from central.security_headers import SecurityHeadersMiddleware  # noqa: E402

STREAMLIT = {"glowtbook": 8503, "explore": 8502, "admin": 8501}
FILES = {"/": "landing-index.html", "/paper.css": "paper.css", "/splat.html": "splat.html",
         "/site.js": "site.js",
         "/logo.svg": "landing-logo.svg", "/shop-prompts.md": "shop-prompts.md",
         "/SHOP-PARTS.md": "SHOP-PARTS.md"}


def _file(name):
    async def view(request):
        p = DEPLOY / name
        return FileResponse(p) if p.exists() else PlainTextResponse("not found", 404)
    return view


async def page(request):
    name = request.path_params["page"]
    p = DEPLOY / f"{name}.html"
    if p.exists():
        return FileResponse(p)
    return PlainTextResponse("not found", 404)


def _redirect(app_name):
    async def view(request):
        tail = request.path_params.get("tail", "")
        q = ("?" + request.url.query) if request.url.query else ""
        return RedirectResponse(f"http://127.0.0.1:{STREAMLIT[app_name]}/{app_name}/{tail}{q}")
    return view


def _admin_off():
    """The admin console is a write surface. On a public test URL it stays off."""
    body = (
        "<!doctype html><meta charset=utf-8><title>Admin is off on this test site</title>"
        "<p>The admin console is not running on this test site. "
        "On a public link it would be open to anyone.</p>"
        "<p><a href=\"/\">Back to the homepage</a></p>"
    ).encode()

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/html; charset=utf-8"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body, "more_body": False})

    return app


routes = [Mount("/api", app=api_app)]
routes += [Route(path, _file(name)) for path, name in FILES.items()]
for sub in ("fingerprint-web", "barcoding", "shop-diagrams", "pwa", "img", "splat"):
    if (DEPLOY / sub).exists():
        mount = "/fingerprint" if sub == "fingerprint-web" else f"/{sub}"
        routes.append(Mount(mount, app=StaticFiles(directory=DEPLOY / sub)))
if (DEPLOY / "blog").exists():   # html=True: /blog/ serves index.html like the proxy does
    routes.append(Mount("/blog", app=StaticFiles(directory=DEPLOY / "blog", html=True)))
# On a laptop, send the browser to the Streamlit port. On Render
# (GLASSDB_PROXY_APPS=1) the visitor cannot reach that port, so forward it.
if os.environ.get("GLASSDB_PROXY_APPS") == "1":
    from scripts.local_proxy import streamlit_proxy  # noqa: E402
    routes.append(Mount("/explore", app=streamlit_proxy(STREAMLIT["explore"], "/explore")))
    routes.append(Mount("/glowtbook", app=streamlit_proxy(STREAMLIT["glowtbook"], "/glowtbook")))
    routes.append(Mount("/admin", app=_admin_off()))
else:
    for name in STREAMLIT:
        routes.append(Route(f"/{name}/", _redirect(name)))
        routes.append(Route(f"/{name}/{{tail:path}}", _redirect(name)))
routes.append(Route("/{page}.html", page))
routes.append(Route("/{page}", page))   # /games -> games.html, like the proxy

site = Starlette(routes=routes, middleware=[Middleware(SecurityHeadersMiddleware)])

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    print(f"Glass Database dev site -> http://127.0.0.1:{port}/   (API at /api/, docs at /api/docs)")
    uvicorn.run(site, host="127.0.0.1", port=port)
