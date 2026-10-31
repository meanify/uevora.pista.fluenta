"""HTTP server for the HTML dashboards and their read-only JSON API.

Pages and assets are served from ``frontend/``; each page calls
``/api/<dashboard>``, which queries PostgreSQL through the cached frames in
``queries``. Nothing outside ``frontend/`` is ever served.
"""

import argparse
import hashlib
import json
import logging
import math
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from sqlalchemy.exc import SQLAlchemyError

from . import database
from . import queries
from .dashboards import ROUTES


WEB_DIR = Path(__file__).resolve().parent.parent / "frontend"
WEB_SUFFIXES = {".html", ".css", ".js"}
LOGGER = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parent


def code_fingerprint():
    """Hash of the backend source on disk, to tell when the running code is stale."""
    digest = hashlib.sha256()
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        digest.update(path.relative_to(BACKEND_DIR).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


# Fingerprint of the code this process is running (read once, at import).
RUNNING_CODE = code_fingerprint()


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def handle_api(data, name, params):
    """Return (status, payload) for an API request."""
    route = ROUTES.get(name)
    if route is None:
        return HTTPStatus.NOT_FOUND, {"erro": f"Dashboard desconhecido: {name}"}
    try:
        frames = data.frames(refresh=params.get("refresh") == ["1"])
        payload = route(frames, params)
    except queries.BadRequest as exc:
        return HTTPStatus.BAD_REQUEST, {"erro": str(exc)}
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        LOGGER.exception("Dashboard query failed")
        return HTTPStatus.BAD_GATEWAY, {"erro": f"Falha ao consultar a base de dados: {type(exc).__name__}"}
    payload["carregado_em"] = data.loaded_at
    payload.setdefault("atualizado", frames["info"]["atualizado"])
    # The pages warn when the backend files changed after the server started.
    payload["versao"] = RUNNING_CODE
    payload["servidor_desatualizado"] = code_fingerprint() != RUNNING_CODE
    return HTTPStatus.OK, _json_safe(payload)


def is_web_file(path):
    """True for a page or asset inside WEB_DIR; "/" is index.html."""
    parts = [p for p in unquote(path).split("/") if p] or ["index.html"]
    if any(p.startswith(".") for p in parts):
        return False
    target = WEB_DIR.joinpath(*parts).resolve()
    return (target.is_relative_to(WEB_DIR) and target.suffix in WEB_SUFFIXES
            and target.is_file())


def make_handler(data):
    class DashboardHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB_DIR), **kwargs)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path.startswith("/api/"):
                status, payload = handle_api(data, url.path[len("/api/"):], parse_qs(url.query))
                body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if not is_web_file(url.path):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            super().do_GET()

        def end_headers(self):
            # Pages and assets change together; make the browser revalidate them
            # so it never mixes a new page with a cached old common.js.
            if not urlsplit(self.path).path.startswith("/api/"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def list_directory(self, path):
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format, *args):
            LOGGER.info("%s - %s", self.address_string(), format % args)

    return DashboardHandler


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Serve the HTML tourism dashboards.")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8050, help="Port to listen on (default: 8050).")
    parser.add_argument("--ttl", type=int, default=1800,
                        help="Seconds before the database tables are read again (default: 1800).")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    database.load_environment()
    data = queries.DashboardData(database.get_engine, ttl=args.ttl)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(data))
    LOGGER.info("Dashboards em http://%s:%s/", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
