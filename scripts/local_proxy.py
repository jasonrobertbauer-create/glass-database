"""
Forward /explore and /glowtbook to the Streamlit processes on this machine.

The local dev server redirects the browser to 127.0.0.1, which only works on
the same computer. On Render the visitor is somewhere else, so those paths
have to be forwarded by the one public server. Used when GLASSDB_PROXY_APPS=1.
"""
from __future__ import annotations

HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length",
    "content-encoding",
}


def streamlit_proxy(port: int, prefix: str):
    """An ASGI app mounted at `prefix` that talks to Streamlit on `port`."""

    def _path(scope) -> str:
        # Mount leaves the full path in scope and records the mount in root_path.
        full = scope.get("path") or "/"
        root = scope.get("root_path") or ""
        rel = full[len(root):] if root and full.startswith(root) else full
        if not rel.startswith("/"):
            rel = "/" + rel
        if rel == "/":
            return prefix + "/"
        return prefix + rel

    def _query(scope) -> str:
        raw = scope.get("query_string") or b""
        return ("?" + raw.decode("latin1")) if raw else ""

    async def app(scope, receive, send):
        if scope["type"] == "http":
            await _http(scope, receive, send, port, _path(scope) + _query(scope))
        elif scope["type"] == "websocket":
            await _ws(scope, receive, send, port, _path(scope) + _query(scope))
        else:
            return

    return app


def _starting(kind: str) -> bytes:
    if kind == "html":
        return (
            "<!doctype html><meta charset=utf-8><title>Starting</title>"
            "<p>This page is still starting. Wait a few seconds and refresh.</p>"
        ).encode()
    return b"This page is still starting. Wait a few seconds and refresh."


async def _http(scope, receive, send, port: int, target: str):
    import httpx
    from starlette.requests import Request

    request = Request(scope, receive)
    headers = []
    for key, value in scope.get("headers") or []:
        name = key.decode("latin1")
        if name.lower() in HOP or name.lower() == "host":
            continue
        headers.append((name, value.decode("latin1")))
    headers.append(("host", f"127.0.0.1:{port}"))
    body = await request.body()
    url = f"http://127.0.0.1:{port}{target}"
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            resp = await client.request(request.method, url, headers=headers, content=body)
    except httpx.HTTPError:
        payload = _starting("html")
        await send({"type": "http.response.start", "status": 503,
                    "headers": [(b"content-type", b"text/html; charset=utf-8"),
                                (b"content-length", str(len(payload)).encode())]})
        await send({"type": "http.response.body", "body": payload, "more_body": False})
        return
    out = []
    for key, value in resp.headers.multi_items():
        if key.lower() in HOP:
            continue
        if key.lower() == "location":
            value = value.replace(f"http://127.0.0.1:{port}", "").replace(f"http://localhost:{port}", "")
        out.append((key.encode("latin1"), value.encode("latin1")))
    await send({"type": "http.response.start", "status": resp.status_code, "headers": out})
    await send({"type": "http.response.body", "body": resp.content, "more_body": False})


async def _ws(scope, receive, send, port: int, target: str):
    import websockets
    from starlette.websockets import WebSocket

    ws = WebSocket(scope, receive, send)
    # Streamlit names a protocol. The browser drops the socket if we don't echo it.
    offered = list(scope.get("subprotocols") or [])
    await ws.accept(subprotocol=offered[0] if offered else None)
    url = f"ws://127.0.0.1:{port}{target}"
    try:
        upstream = await websockets.connect(
            url, open_timeout=20, max_size=None,
            subprotocols=offered or None)
    except Exception:
        await ws.close(code=1013)
        return
    import asyncio

    async def client_to_upstream():
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    await upstream.send(message["text"])
                elif message.get("bytes") is not None:
                    await upstream.send(message["bytes"])
        except Exception:
            pass
        finally:
            await upstream.close()

    async def upstream_to_client():
        try:
            async for message in upstream:
                if isinstance(message, str):
                    await ws.send_text(message)
                else:
                    await ws.send_bytes(message)
        except Exception:
            pass

    try:
        await asyncio.gather(client_to_upstream(), upstream_to_client())
    finally:
        try:
            await ws.close()
        except Exception:
            pass
