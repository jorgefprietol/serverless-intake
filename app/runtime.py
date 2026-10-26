"""Local service host: atomic requests, durable audit and bounded HTTP input."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import math
import os
import re
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = logging.getLogger("service")
MAX_BODY = 262144


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class Store:
    def __init__(self, path="var/service.db", initialize=True):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        if initialize:
            self.initialize()

    def initialize(self):
        try:
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
              key TEXT PRIMARY KEY, digest TEXT NOT NULL, response TEXT NOT NULL,
              elapsed_ms REAL NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL,
              created_at TEXT NOT NULL);
            """)
        except BaseException:
            self.connection.close()
            raise

    def event(self, kind, data):
        self.connection.execute("INSERT INTO events(kind,data,created_at) VALUES(?,?,?)",
                                (kind, encode(data), datetime.now(timezone.utc).isoformat()))

    def close(self):
        self.connection.close()

    def run(self, payload, key, process):
        if not isinstance(payload, dict):
            raise ValueError("El cuerpo debe ser un objeto JSON")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
            raise ValueError("Idempotency-Key requerido: 1-128 caracteres alfanuméricos, . _ : -")
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        start = time.perf_counter()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute("SELECT * FROM requests WHERE key=?", (key,)).fetchone()
            if row:
                if not hmac.compare_digest(row["digest"], digest):
                    raise Conflict("Idempotency-Key ya utilizado con otro contenido")
                self.connection.commit()
                return json.loads(row["response"]), True
            result = process(payload, self)
            response = {"request_id": key, "result": result}
            serialized = encode(response)
            elapsed = round((time.perf_counter() - start) * 1000, 3)
            self.connection.execute("INSERT INTO requests VALUES(?,?,?,?,?)", (
                key, digest, serialized, elapsed, datetime.now(timezone.utc).isoformat()))
            self.connection.commit()
            return response, False
        except BaseException:
            self.connection.rollback()
            raise

    def metrics(self):
        durations = sorted(r[0] for r in self.connection.execute("SELECT elapsed_ms FROM requests"))
        return {
            "scope": "local_observed_requests",
            "completed_requests": len(durations),
            "p50_ms": durations[math.ceil(len(durations)*.5)-1] if durations else None,
            "p95_ms": durations[math.ceil(len(durations)*.95)-1] if durations else None,
            "audit_events": self.connection.execute("SELECT count(*) FROM events").fetchone()[0],
            "measurement": "Successful unique transactions; excludes network time, errors and replays",
        }


class Conflict(ValueError):
    pass


def handler(domain, db_path, token):
    initial = Store(db_path)
    initial.close()
    class Handler(BaseHTTPRequestHandler):
        server_version = "OperationsService/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, message, *args):
            LOG.info("http method=%s status=%s", self.command, args[1] if len(args)>1 else "-")

        def send(self, status, value, content_type="application/json; charset=utf-8", extra=None):
            raw = value.encode() if isinstance(value, str) else encode(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for key, val in (extra or {}).items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + token).encode())

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self.send(200, {"status": "ok"})
            elif path in ("/", "/assets/style.css", "/assets/app.js"):
                file, mime = {"/": ("index.html", "text/html"),
                              "/assets/style.css": ("style.css", "text/css"),
                              "/assets/app.js": ("app.js", "text/javascript")}[path]
                self.send(200, Path(__file__).with_name("web").joinpath(file).read_text(encoding="utf-8"), mime+"; charset=utf-8")
            elif path == "/api/config":
                self.send(200, {"title": domain.TITLE, "description": domain.DESCRIPTION, "demo": domain.DEMO,
                                "backend": os.getenv("MODEL_BACKEND", "local")})
            elif path == "/api/metrics":
                if not self.authorized():
                    return self.send(401, {"error": "Se requiere token de servicio"})
                store = Store(db_path, initialize=False)
                try:
                    self.send(200, store.metrics())
                finally:
                    store.close()
            else:
                self.send(404, {"error": "Ruta desconocida"})

        def do_POST(self):
            if self.path != "/api/run":
                return self.send(404, {"error": "Ruta desconocida"})
            if not self.authorized():
                return self.send(401, {"error": "Se requiere token de servicio"})
            try:
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("Transfer-Encoding no soportado")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY:
                    return self.send(413, {"error": "Cuerpo vacío o mayor a 256 KiB"})
                if self.headers.get_content_type() != "application/json":
                    return self.send(415, {"error": "Content-Type debe ser application/json"})
                payload = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Número JSON inválido")))
                store = Store(db_path, initialize=False)
                try:
                    response, replay = store.run(payload, self.headers.get("Idempotency-Key"), domain.process)
                finally:
                    store.close()
                self.send(200, response, extra={"Idempotency-Replayed": str(replay).lower()})
            except Conflict as exc:
                self.send(409, {"error": str(exc)})
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                self.send(422, {"error": str(exc)[:300]})
            except Exception:
                LOG.error("request_failed type=internal")
                self.send(500, {"error": "Error interno; la transacción se revirtió"})
    return Handler


def main():
    from . import domain
    parser = argparse.ArgumentParser(description=domain.DESCRIPTION)
    parser.add_argument("command", choices=["demo", "serve", "run", "metrics"], nargs="?", default="demo")
    parser.add_argument("--db", default=os.getenv("DATABASE_PATH", "var/service.db"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--key", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.command == "serve":
        token = os.getenv("SERVICE_TOKEN", "")
        if len(token) < 24:
            parser.error("Configure SERVICE_TOKEN con al menos 24 caracteres")
        server = ThreadingHTTPServer((args.host, args.port), handler(domain, args.db, token))
        LOG.info("listening http://%s:%s", args.host, server.server_port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return
    if args.command == "demo":
        Path("var").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="demo-", dir="var") as temp:
            store = Store(Path(temp)/"demo.db")
            try:
                result, _ = store.run(domain.DEMO, "demo-001", domain.process)
                print(json.dumps({"dataset": "synthetic", **result, "metrics": store.metrics()}, indent=2, ensure_ascii=False))
            finally:
                store.close()
        return
    store = Store(args.db)
    try:
        if args.command == "metrics":
            result = store.metrics()
        else:
            if not args.input:
                parser.error("run requiere --input archivo.json")
            result, _ = store.run(json.loads(args.input.read_text(encoding="utf-8")), args.key or str(uuid.uuid4()), domain.process)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        store.close()
