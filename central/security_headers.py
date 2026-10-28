"""
Response headers for the public site.

Apache and nginx set the same values (deploy/apache-glassdatabase-proxy.conf,
deploy/nginx-glassdatabase.conf) so static pages, Streamlit and the API agree.
This middleware covers the API and the local dev server when those configs
aren't in front.

The Content-Security-Policy is loose enough for the pages that already exist:
inline scripts (the static pages and Streamlit), Google fonts, the studios map
(Leaflet on unpkg, CARTO tiles), the 3D photo viewer and the fingerprint
camera (jsDelivr + Hugging Face for the on-device model, a blob worker, and
the camera itself). It still blocks framing by other sites and plugins.
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders

# One line, no double quotes, so it can be pasted into the Apache/nginx configs.
CSP = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "form-action 'self' https://accounts.google.com; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: "
    "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com; "
    "connect-src 'self' blob: data: wss: ws: "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com "
    "https://fonts.googleapis.com https://fonts.gstatic.com "
    "https://huggingface.co https://*.huggingface.co https://*.hf.co "
    "https://basemaps.cartocdn.com https://*.basemaps.cartocdn.com; "
    "worker-src 'self' blob:; child-src 'self' blob:; "
    "frame-src 'self' blob: https://accounts.google.com; "
    "media-src 'self' blob: data:; manifest-src 'self'"
)

# camera=(self) keeps the fingerprint capture apps working. Features not listed
# stay at the browser default.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self)",
    "Content-Security-Policy": CSP,
}

HSTS_VALUE = "max-age=15552000"


class SecurityHeadersMiddleware:
    """Add the headers above. HSTS only when the request itself is HTTPS."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        https = scope.get("scheme") == "https"
        if not https:
            for key, value in scope.get("headers") or []:
                if key == b"x-forwarded-proto":
                    https = value.decode("latin1").split(",")[0].strip() == "https"
                    break

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                for key, value in SECURITY_HEADERS.items():
                    headers[key] = value
                if https:
                    headers["Strict-Transport-Security"] = HSTS_VALUE
            await send(message)

        await self.app(scope, receive, send_with_headers)
