"""
Start the site the way the free Render test service does.

One public port (Render sets PORT). The static pages and the API listen there.
Find Artists & Studios and Glowtbook run beside it and are forwarded through
that same port. The database is a fresh copy of the invented demo each time
this process starts — Render's free plan forgets files whenever the service
sleeps, so nothing typed into the test site is kept.

    PORT=8090 python -m scripts.render_start
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Set before any app import. The API reads ROOT_PATH when it is imported.
os.environ.setdefault("GLASSDB_PROXY_APPS", "1")
os.environ.setdefault("ROOT_PATH", "/api")
os.environ.setdefault("GLASSDB_MODERATION", "1")
os.environ.setdefault("GLASSDB_PATH", str(ROOT / "data" / "glassdb.db"))
if not os.environ.get("PUBLIC_BASE_URL"):
    external = (os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if external:
        os.environ["PUBLIC_BASE_URL"] = external

APPS = (
    ("explore/app.py", "8502", "explore"),
    ("glowtbook/app.py", "8503", "glowtbook"),
)
_CHILDREN: list[subprocess.Popen] = []


def _stop(*_args) -> None:
    for proc in _CHILDREN:
        if proc.poll() is None:
            proc.terminate()


def _seed() -> None:
    path = Path(os.environ["GLASSDB_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    for extra in ("", "-wal", "-shm"):
        candidate = Path(str(path) + extra) if extra else path
        if candidate.exists():
            candidate.unlink()
    from scripts.seed_demo import seed
    print("Seeding a fresh demo database (invented names only) at", seed(), flush=True)


def _streamlit(script: str, port: str, base: str) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(ROOT / script),
        "--server.port", port,
        "--server.address", "127.0.0.1",
        "--server.baseUrlPath", base,
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
        "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false",
    ]
    return subprocess.Popen(cmd, cwd=str(ROOT))


def main() -> None:
    _seed()
    for script, port, base in APPS:
        print(f"Starting {base} on 127.0.0.1:{port}", flush=True)
        _CHILDREN.append(_streamlit(script, port, base))
    # Give Streamlit a head start, but don't hold the public port shut.
    time.sleep(2)
    import uvicorn

    from scripts.dev_site import site
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Glass Database test site -> http://{host}:{port}/", flush=True)
    try:
        uvicorn.run(site, host=host, port=port)
    finally:
        _stop()


if __name__ == "__main__":
    main()
