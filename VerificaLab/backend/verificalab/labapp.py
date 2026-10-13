"""Aplicação de laboratório descartável — alvo de demonstração do VerificaLab.

Iniciada pela plataforma em loopback e porta específica (127.0.0.1:8477).
Controla os próprios acessos: recusa cliente que não seja loopback e Host
que não seja loopback. Rotas documentadas:

  GET  /ok                200 JSON normal
  GET  /json              200 JSON com contrato de campos
  GET  /text              200 text/plain
  GET  /error             500 erro controlado
  GET  /forbidden         403 negação de acesso
  GET  /slow?delay=N      200 após N segundos (teto 10)
  GET  /redirect-local    302 para /ok (mesma origem)
  GET  /redirect-external 302 para http://example.com/ (DEVE ser bloqueado
                          pelo VerificaLab antes da chamada)
  GET  /drop              conexão encerrada sem resposta
  GET  /headers           200 SEM cabeçalhos de segurança (intencional)
  GET  /echo-headers      200 ecoa cabeçalhos da requisição
  POST /echo              200 ecoa corpo JSON

Falhas intencionais aparecem como falha no relatório — a plataforma não
mascara resultado para ficar verde.
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

LAB_VERSION = "1.0.0"
MAX_DELAY = 10.0


def _loopback_ok(handler: BaseHTTPRequestHandler) -> bool:
    host = (handler.headers.get("Host") or "").lower()
    hostname = host.rsplit(":", 1)[0]
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]
    if hostname not in ("127.0.0.1", "localhost", "::1"):
        return False
    peer = handler.client_address[0]
    return peer.startswith("127.") or peer == "::1"


class LabHandler(BaseHTTPRequestHandler):
    server_version = f"VerificaLab-Lab/{LAB_VERSION}"
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        print(f"[lab] TCP {self.client_address[0]}", flush=True)

    def log_message(self, fmt: str, *args) -> None:  # sem query string no log
        path = urlsplit(self.path).path
        print(f"[lab] {self.command} {path}", flush=True)

    def _send(self, status: int, body: bytes, ctype: str,
              extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Date", time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                               time.gmtime()))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    def _json(self, status: int, obj: dict, extra: dict | None = None) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", extra)

    def _deny(self) -> None:
        self._json(403, {"error": "acesso negado pelo laboratório",
                         "detail": "somente loopback é aceito"})

    def do_GET(self) -> None:  # noqa: N802
        self._route("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._route("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    def _route(self, method: str) -> None:
        if not _loopback_ok(self):
            self._deny()
            return
        parts = urlsplit(self.path)
        path = parts.path
        qs = parse_qs(parts.query)

        if method in ("GET", "HEAD"):
            if path == "/":
                self._json(200, {
                    "service": "verificalab-lab", "version": LAB_VERSION,
                    "routes": ["/ok", "/json", "/text", "/error", "/forbidden",
                               "/slow?delay=N", "/redirect-local",
                               "/redirect-external", "/drop", "/headers",
                               "/echo-headers"],
                })
            elif path == "/ok":
                self._json(200, {"status": "ok", "service": "verificalab-lab"})
            elif path == "/json":
                self._json(200, {
                    "service": "verificalab-lab", "version": LAB_VERSION,
                    "status": "running",
                    "checks": {"database": "ok", "cache": "ok"},
                })
            elif path == "/text":
                self._send(200, b"verificalab-lab resposta normal\n",
                           "text/plain; charset=utf-8")
            elif path == "/error":
                self._json(500, {"error": "falha controlada",
                                 "detail": "rota de erro intencional do lab"})
            elif path == "/forbidden":
                self._json(403, {"error": "acesso negado",
                                 "detail": "rota de negação intencional"})
            elif path == "/slow":
                try:
                    delay = float(qs.get("delay", ["2"])[0])
                except ValueError:
                    delay = 2.0
                delay = max(0.0, min(delay, MAX_DELAY))
                time.sleep(delay)
                self._json(200, {"status": "ok", "slept_s": delay})
            elif path == "/redirect-local":
                self._send(302, b"", "text/plain", {"Location": "/ok"})
            elif path == "/redirect-external":
                self._send(302, b"", "text/plain",
                           {"Location": "http://example.com/"})
            elif path == "/drop":
                try:
                    self.wfile.flush()
                    self.connection.close()
                except OSError:
                    pass
                self.close_connection = True
                return
            elif path == "/headers":
                # intencionalmente SEM cabeçalhos de segurança
                self._json(200, {"status": "ok",
                                 "note": "rota sem cabeçalhos de segurança"})
            elif path == "/echo-headers":
                self._json(200, {"headers": dict(self.headers)})
            else:
                self._json(404, {"error": "rota inexistente", "path": path})
            return

        if path == "/echo":  # POST
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(length, 65536)) if length else b"{}"
            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json(400, {"error": "JSON inválido"})
                return
            self._json(200, {"echo": data})
        else:
            self._json(404, {"error": "rota inexistente", "path": path})


def main() -> None:
    parser = argparse.ArgumentParser(description="Laboratório VerificaLab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8477)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost"):
        raise SystemExit("lab: somente loopback é permitido")
    server = ThreadingHTTPServer((args.host, args.port), LabHandler)
    print(f"[lab] verificalab-lab ouvindo em http://{args.host}:{args.port}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
