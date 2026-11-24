"""Paikallinen HTTP-silta Chrome Web Speech API (`webkitSpeechRecognition`) -puheentunnistukselle."""

from collections.abc import Callable
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any
import webbrowser

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 8192
LOCALHOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 48765
BRIDGE_WINDOW_TITLE = "Puhis – Chrome-puhekuuntelu"

type BridgeCandidatesCallback = Callable[[list[str]], None]
type BridgeStatusCallback = Callable[[str], None]

_BRIDGE_HTML = """<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="utf-8">
<title>Puhis – Chrome-puhekuuntelu</title>
<style>
  body { font-family: "Segoe UI", sans-serif; background: #111827; color: #F8FAFC;
         margin: 0; padding: 28px; display: flex; justify-content: center; }
  .card { max-width: 620px; width: 100%; background: #1F2937; border-radius: 14px;
          padding: 24px; border: 1px solid #374151; box-shadow: 0 12px 30px rgba(0,0,0,0.35); }
  h1 { margin: 0 0 8px; font-size: 20px; }
  p { color: #CBD5E1; margin: 0 0 16px; line-height: 1.45; }
  .row { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
  button { background: #10B981; color: #06281E; border: none; border-radius: 8px;
           padding: 10px 18px; font-size: 15px; font-weight: 700; cursor: pointer; }
  button.stop { background: #EF4444; color: #FFFFFF; }
  .status { font-weight: 600; color: #6EE7B7; }
  .interim { min-height: 24px; color: #FDE68A; font-style: italic; margin-bottom: 12px; }
  .log { background: #0F172A; border-radius: 8px; padding: 12px; height: 220px;
         overflow-y: auto; font-family: Consolas, monospace; font-size: 13px; }
  .log div { padding: 3px 0; border-bottom: 1px solid #1E293B; }
</style>
</head>
<body>
<div class="card">
  <h1>🐱 Puhis – Chrome-puhekuuntelu (fi-FI)</h1>
  <p>Tämä välilehti käyttää Chromen omaa jatkuvaa puheentunnistusta ja lähettää tunnistetun puheen
     suoraan Puhikselle. Pidä välilehti auki taustalla ja puhu normaalisti.</p>
  <div class="row">
    <button id="toggleBtn">Käynnistä kuuntelu</button>
    <span id="status" class="status">Valmis käynnistettäväksi</span>
  </div>
  <div id="interim" class="interim"></div>
  <div id="log" class="log"></div>
</div>
<script>
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
const btn = document.getElementById("toggleBtn");
const statusEl = document.getElementById("status");
const interimEl = document.getElementById("interim");
const logEl = document.getElementById("log");

let active = false;
let rec = null;
let lastAborted = false;

// Suljetaan mahdollinen aiempi Chrome-kuunteluikkuna, jotteivät kaksi välilehteä
// taistele mikrofonista (error:aborted).
const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("puhis_speech") : null;
if (channel) {
  channel.postMessage("takeover");
  channel.onmessage = (ev) => {
    if (ev.data === "takeover") {
      active = false;
      if (rec) { try { rec.stop(); } catch (_) {} }
      window.close();
    }
  };
}

function addLog(text) {
  const row = document.createElement("div");
  row.textContent = new Date().toLocaleTimeString("fi-FI") + "  " + text;
  logEl.prepend(row);
  while (logEl.children.length > 40) logEl.removeChild(logEl.lastChild);
}

async function sendCandidates(candidates) {
  try {
    await fetch("/utterance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidates })
    });
  } catch (err) {
    statusEl.textContent = "Yhteys Puhikseen katkesi";
  }
}

function startRecognition() {
  if (!SpeechRec) {
    statusEl.textContent = "Selaimesi ei tue Web Speech APIa (käytä Chromea tai Edgeä).";
    return;
  }
  rec = new SpeechRec();
  rec.lang = "fi-FI";
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 5;

  rec.onstart = () => {
    lastAborted = false;
    statusEl.textContent = "🟢 Kuuntelee jatkuvasti (fi-FI)…";
    fetch("/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: "listening" })
    }).catch(() => {});
  };
  rec.onerror = (ev) => {
    const err = ev && ev.error ? ev.error : "unknown";
    if (err === "aborted") {
      lastAborted = true;
    }
    fetch("/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: "error:" + err })
    }).catch(() => {});
    if (err === "not-allowed" || err === "service-not-allowed") {
      active = false;
      updateButton();
      statusEl.textContent = "Napsauta 'Käynnistä kuuntelu' ja salli mikrofoni";
    } else if (err !== "no-speech" && err !== "aborted") {
      statusEl.textContent = "Virhe: " + err;
    }
  };
  rec.onend = () => {
    if (active) {
      const delay = lastAborted ? 600 : 150;
      setTimeout(() => { if (active) startRecognition(); }, delay);
    } else {
      statusEl.textContent = "Pysäytetty";
    }
  };
  rec.onresult = (ev) => {
    let interim = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const res = ev.results[i];
      if (res.isFinal) {
        const candidates = [];
        for (let j = 0; j < res.length; j++) {
          const t = (res[j].transcript || "").trim();
          if (t && !candidates.includes(t)) candidates.push(t);
        }
        if (candidates.length > 0) {
          addLog(candidates[0]);
          sendCandidates(candidates);
        }
        interimEl.textContent = "";
      } else {
        interim += res[0].transcript;
      }
    }
    if (interim) interimEl.textContent = "… " + interim;
  };
  try {
    rec.start();
  } catch (err) {
    active = false;
    updateButton();
    statusEl.textContent = "Napsauta 'Käynnistä kuuntelu' aloittaaksesi";
  }
}

function updateButton() {
  btn.textContent = active ? "Pysäytä kuuntelu" : "Käynnistä kuuntelu";
  btn.classList.toggle("stop", active);
}

btn.addEventListener("click", () => {
  active = !active;
  updateButton();
  if (active) {
    startRecognition();
  } else if (rec) {
    rec.stop();
  }
});

// Suljetaan apuikkuna automaattisesti, jos Puhis sammutetaan.
setInterval(() => {
  fetch("/ping", { cache: "no-store" }).catch(() => {
    active = false;
    updateButton();
    if (rec) { try { rec.stop(); } catch (_) {} }
    statusEl.textContent = "Puhis suljettu.";
    window.close();
  });
}, 1000);

// Käynnistetään kuuntelu suoraan sivun latautuessa ilman erillistä klikkausta.
window.addEventListener("load", () => {
  if (!active) {
    active = true;
    updateButton();
    startRecognition();
  }
});
</script>
</body>
</html>
"""


class _BridgeHandler(BaseHTTPRequestHandler):
    """Käsittelee paikallisen selainsillan HTTP-pyynnöt."""

    def __init__(
        self,
        *args: Any,
        on_candidates: BridgeCandidatesCallback,
        on_status: BridgeStatusCallback | None = None,
        **kwargs: Any,
    ) -> None:
        self._on_candidates = on_candidates
        self._on_status = on_status
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.debug("BrowserBridge: " + format, *args)

    def do_GET(self) -> None:
        if self.path == "/ping":
            payload = b'{"ok":true}'
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path not in ("/", "/index.html"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = _BRIDGE_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path not in ("/utterance", "/status"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE if length > MAX_BODY_BYTES else HTTPStatus.BAD_REQUEST)
            return

        raw_body = self.rfile.read(length)
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/status":
            state = data.get("state") if isinstance(data, dict) else None
            if isinstance(state, str) and state.strip() and self._on_status is not None:
                self._on_status(state.strip())
        else:
            candidates = _parse_bridge_payload(data)
            if candidates:
                logger.info("Chrome-tunnistus: %r", candidates[0])
                self._on_candidates(candidates)

        response = b'{"ok":true}'
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


def _parse_bridge_payload(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    raw_list = data.get("candidates")
    if isinstance(raw_list, list):
        return [str(item).strip() for item in raw_list if isinstance(item, str) and item.strip()]
    single = data.get("text")
    if isinstance(single, str) and single.strip():
        return [single.strip()]
    return []


class BrowserSpeechBridge:
    """Paikallinen HTTP-palvelin (`127.0.0.1`), joka vastaanottaa Chromen Web Speech -tulokset."""

    def __init__(
        self,
        on_candidates: BridgeCandidatesCallback,
        on_status: BridgeStatusCallback | None = None,
        port: int = 0,
    ) -> None:
        self._on_candidates = on_candidates
        self._on_status = on_status
        self._port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        if self._server is None:
            return ""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/"

    def start(self) -> str:
        """Käynnistää HTTP-sillan taustasäikeessä ja palauttaa sen URL-osoitteen."""
        if self._server is not None:
            return self.url
        handler = partial(
            _BridgeHandler,
            on_candidates=self._on_candidates,
            on_status=self._on_status,
        )
        try:
            self._server = ThreadingHTTPServer((LOCALHOST, self._port), handler)
        except OSError:
            if self._port == 0:
                raise
            # Jos kiinteä portti on varattu, käytetään käyttöjärjestelmän vapaata porttia.
            self._server = ThreadingHTTPServer((LOCALHOST, 0), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="puhis-browser-bridge",
            daemon=True,
        )
        self._thread.start()
        logger.info("Selainpuhesilta käynnistyi osoitteessa %s", self.url)
        return self.url

    def stop(self) -> None:
        """Sulkee HTTP-sillan hallitusti."""
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)


def find_chrome_executable() -> str | None:
    """Etsii Google Chromen suoritettavan tiedoston Windowsissa."""
    candidates: list[Path] = []
    for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env_var, "").strip()
        if base:
            candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for path in candidates:
        if path.is_file():
            return str(path)
    return shutil.which("chrome") or shutil.which("chrome.exe")


def launch_chrome_app(url: str) -> bool:
    """Avaa selainkuuntelun kevyessä Chrome `--app`-ikkunassa (tai oletusselaimessa)."""
    chrome = find_chrome_executable()
    if chrome is not None:
        try:
            subprocess.Popen(
                [chrome, f"--app={url}", "--window-size=480,320"],
                shell=False,
            )
            return True
        except OSError:
            logger.exception("Chromen käynnistys --app-tilassa epäonnistui")
    webbrowser.open(url)
    return False
