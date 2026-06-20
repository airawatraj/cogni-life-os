from __future__ import annotations

import json
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .auth import TokenStore
from .config import Settings
from .evaluation import run as run_eval
from .indexer import Index
from .ingest import capture_text
from .ingest import capture_binary
from .integrity import scan
from .vault import Vault


APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cogni Life OS</title>
  <link rel="manifest" href="/manifest.json">
  <style>
    :root { color-scheme: light dark; font-family: Inter, system-ui, -apple-system, sans-serif; }
    body { margin: 0; background: #f7f7f4; color: #1d2525; }
    main { max-width: 980px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
    h1 { font-size: 28px; margin: 0; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
    section { background: white; border: 1px solid #d9ddd6; border-radius: 8px; padding: 16px; }
    textarea, input { width: 100%; box-sizing: border-box; border: 1px solid #bdc6bf; border-radius: 6px; padding: 10px; font: inherit; }
    button { border: 0; border-radius: 6px; padding: 10px 14px; background: #205f5f; color: white; font: inherit; cursor: pointer; }
    .lights { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .light { padding: 12px; border-radius: 6px; color: #101414; background: #d8ead1; }
    .amber { background: #ffe3a3; }
    .red { background: #ffd0cd; }
    pre { white-space: pre-wrap; max-height: 360px; overflow: auto; }
    @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } main { padding: 14px; } }
  </style>
</head>
<body>
<main>
  <header><h1>Cogni Life OS</h1><button onclick="refresh()">Refresh</button></header>
  <div class="grid">
    <section>
      <h2>Capture</h2>
      <textarea id="capture" rows="8" placeholder="Capture text, links, decisions, commitments, or notes"></textarea>
      <p><button onclick="captureText()">Capture</button></p>
      <pre id="captureOut"></pre>
    </section>
    <section>
      <h2>Search</h2>
      <input id="query" placeholder="Search the vault">
      <p><button onclick="searchVault()">Search</button></p>
      <pre id="searchOut"></pre>
    </section>
    <section>
      <h2>Dashboard</h2>
      <div class="lights">
        <div class="light">Ingestion</div>
        <div class="light amber">Model Gate</div>
        <div class="light" id="integrityLight">Integrity</div>
      </div>
      <pre id="health"></pre>
    </section>
    <section>
      <h2>Operations</h2>
      <p><button onclick="integrity()">Integrity</button> <button onclick="evaluate()">Evaluate</button></p>
      <pre id="opsOut"></pre>
    </section>
  </div>
</main>
<script>
let token = localStorage.getItem("cogni_token") || prompt("Service token");
localStorage.setItem("cogni_token", token);
async function api(path, options={}) {
  options.headers = Object.assign({"Authorization": "Bearer " + token}, options.headers || {});
  const r = await fetch(path, options);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
function show(id, data) { document.getElementById(id).textContent = JSON.stringify(data, null, 2); }
async function captureText() {
  const text = document.getElementById("capture").value;
  show("captureOut", await api("/api/capture-text", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text})}));
}
async function searchVault() { show("searchOut", await api("/api/search?q=" + encodeURIComponent(document.getElementById("query").value))); }
async function integrity() { const r = await api("/api/integrity"); show("opsOut", r); document.getElementById("integrityLight").className = "light " + (r.status === "pass" ? "" : "red"); }
async function evaluate() { show("opsOut", await api("/api/evaluate", {method:"POST"})); }
async function refresh() { show("health", await api("/api/health")); }
refresh();
</script>
</body>
</html>
"""


def make_handler(settings: Settings):
    vault = Vault(settings.vault_path)
    vault.init()
    index = Index(settings.runtime_path / "index.sqlite3")
    tokens = TokenStore(settings.runtime_path / "tokens.json")
    if settings.service_token not in {"", "dev-local-change-me"}:
        tokens.add_existing(settings.service_token, "local-user")

    class Handler(BaseHTTPRequestHandler):
        def _auth(self) -> bool:
            header = self.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
            result = tokens.verify(token)
            if not result.ok:
                return False
            client = self.client_address[0] if self.client_address else "unknown"
            return tokens.rate_limit(result.subject or "unknown", client)

        def _json(self, status: int, data: object) -> None:
            body = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length > settings.max_upload_bytes:
                raise ValueError("upload limit exceeded")
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = APP_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/manifest.json":
                self._json(200, {"name": "Cogni Life OS", "short_name": "Cogni", "start_url": "/", "display": "standalone"})
                return
            if parsed.path.startswith("/api/") and not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            if parsed.path == "/api/health":
                self._json(200, {"vault": str(vault.root), "index": index.health()})
                return
            if parsed.path == "/api/integrity":
                self._json(200, scan(vault))
                return
            if parsed.path == "/api/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                self._json(200, {"results": index.search(query or "source")})
                return
            self._json(404, {"error": "not_found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/") and not self._auth():
                self._json(401, {"error": "unauthorized"})
                return
            try:
                if parsed.path == "/api/capture-text":
                    payload = self._read_json()
                    result = capture_text(vault, payload["text"], channel=payload.get("channel", "pwa"), sender=payload.get("sender", "user"))
                    index.rebuild(vault)
                    self._json(200, result.__dict__)
                    return
                if parsed.path == "/api/upload":
                    payload = self._read_json()
                    result = handle_upload(vault, index, settings, payload)
                    self._json(200, result)
                    return
                if parsed.path == "/api/evaluate":
                    self._json(200, run_eval(settings, live_model=False))
                    return
                if parsed.path == "/api/revoke":
                    header = self.headers.get("Authorization", "")
                    token = header[7:] if header.startswith("Bearer ") else ""
                    tokens.revoke(token)
                    self._json(200, {"status": "revoked"})
                    return
            except Exception as exc:
                self._json(400, {"error": type(exc).__name__, "detail": str(exc)})
                return
            self._json(404, {"error": "not_found"})

    return Handler


def handle_upload(vault: Vault, index: Index, settings: Settings, payload: dict) -> dict:
    raw = base64.b64decode(payload["data_base64"], validate=True)
    if len(raw) > settings.max_upload_bytes:
        raise ValueError("upload limit exceeded")
    result = capture_binary(vault, raw, payload.get("filename", "upload.bin"), channel=payload.get("channel", "pwa"), sender=payload.get("sender", "user"))
    index.rebuild(vault)
    return result


def serve(settings: Settings, host: str, port: int) -> None:
    if settings.service_token in {"", "dev-local-change-me"}:
        raise ValueError("COGNI_SERVICE_TOKEN must be set to a non-default secret before starting the service")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("local phase service may only bind to loopback addresses")
    server = ThreadingHTTPServer((host, port), make_handler(settings))
    print(f"Cogni Life OS listening on http://{host}:{port}")
    print("Service token: [REDACTED]")
    server.serve_forever()
