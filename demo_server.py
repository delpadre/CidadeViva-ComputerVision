"""Servidor de demonstração SEM dependências extras (só biblioteca padrão + o pipeline).

Mesmo contrato da API FastAPI. Uso: python demo_server.py [porta]   ->  http://localhost:8000
"""
import json
import sys
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from citizen_vision.service import ServiceError, extract_from_bytes

WEB = Path(__file__).parent / "web"


def _file_from_multipart(content_type: str, body: bytes) -> bytes:
    msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    for part in msg.iter_parts():
        if part.get_param("name", header="content-disposition") == "file":
            return part.get_payload(decode=True) or b""
    return b""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._json(200, {"status": "ok"})
        if path in ("/", "/index.html"):
            return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        self._json(404, {"detail": "não encontrado"})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/extract-address":
            return self._json(404, {"detail": "não encontrado"})
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        lookup = parse_qs(url.query).get("lookup_ibge", ["false"])[0].lower() == "true"
        try:
            data = _file_from_multipart(self.headers.get("Content-Type", ""), body)
            self._json(200, extract_from_bytes(data, lookup_ibge=lookup))
        except ServiceError as e:
            self._json(e.status, {"detail": e.message})

    def log_message(self, *args):  # sem log de requisições (LGPD)
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"ZeloCidade demo em http://localhost:{port}  (Ctrl+C para sair)")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
