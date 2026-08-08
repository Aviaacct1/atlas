"""Avia Cortex - cockpit server WITH the on-demand QSI route service. Author: Avia Solutions.

Run this INSTEAD of serve.py on the machine that has the QSI tool and its databases (the same
box behind the Cloudflare tunnel). It serves the dashboard and cockpit like serve.py, and adds
one endpoint:

    GET /api/bum?airport=SOU&n=10

which kicks off the real QSI optimiser (route_forecast.forecast) for that airport's candidate
routes in a BACKGROUND THREAD and writes each result into webapp/data/bum_candidates.json as it
finishes. The cockpit already polls that file every few seconds, so an analyst on a laptop over
the tunnel clicks "Run QSI candidates", the compute happens here on the box, and the routes
stream into her BUM tab. She installs nothing.

ACCESS - single shared password (no Cloudflare account needed for guests):
    Every page, the data bundle and the API sit behind HTTP Basic Auth. Guests open the address,
    type the shared password (any username) and they are in. Set the password by either:
      - environment variable  FORECAST_PASSWORD=...   (wins if set), or
      - the first non-comment line of  webapp/access_password.txt.
    Only the password is checked (username ignored), with a constant-time compare. If NEITHER is
    set the server runs OPEN and prints a warning: that is for local development only. The licensed
    data (ACI, Sabre, OAG, Oxford Economics) must never be exposed over the tunnel without the
    password set.

Config. Every data location resolves through avia_forecast/paths.py, which reads
AVIA_QSI_APP and AVIA_DB_ROOT. This module used to carry its own QSI_APP, QSI_OAG and
QSI_SABRE variables, each with its own default, so setting one set and not the other gave
a host with half the tool pointed at the old location. Those three are superseded.

    FORECAST_PASSWORD = the shared access password (overrides access_password.txt)
Run:  set PORT=8000 & python qsi_service.py      (then expose via the tunnel, as for the QSI tool)
"""
import http.server, socketserver, threading, queue, re, os, sys, json, urllib.parse, webbrowser, base64, hmac

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
SCRIPTS = os.path.join(REPO, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, REPO)
from avia_forecast import paths

PORT = int(os.environ.get("PORT", "8000"))
QSI_APP = paths.QSI_APP
# The newest read-only serve copy of the OAG store, refreshed by ingest_all_oag, so the
# service never holds a lock on the live file the ingest writes. Falls back to the store.
QSI_OAG = paths.serve_copy() or paths.OAG_DB
QSI_SABRE = paths.SABRE_DB

REALM = "Avia Cortex"


def _load_password():
    """Shared access password: FORECAST_PASSWORD env wins, else the first non-comment line of
    access_password.txt beside this file. Empty return means no password is set (server open)."""
    pw = (os.environ.get("FORECAST_PASSWORD") or "").strip()
    if pw:
        return pw
    fp = os.path.join(ROOT, "access_password.txt")
    if os.path.exists(fp):
        for line in open(fp, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#"):
                return s
    return ""


ACCESS_PASSWORD = _load_password()

MAX_N = 15                                   # cap optimiser routes per request
_AP_RE = re.compile(r"^[A-Z]{3}$")           # accept only a clean IATA code
_pending = set()                             # airports queued or running (dedupe)
_lock = threading.Lock()
_jobs = queue.Queue()                        # single worker => runs serialise => no file race


def _run_airport(airport, n):
    try:
        import run_qsi_bum as RUNNER          # the incremental real-tool runner
        RUNNER.run([airport], QSI_APP, QSI_OAG, QSI_SABRE, n, None)
    except Exception as e:
        print(f"[qsi] {airport} run failed: {e}")
        try:                                   # surface the failure into the cockpit
            fp = os.path.join(ROOT, "data", "bum_candidates.json")
            import run_qsi_bum as _R
            d = json.load(open(fp)) if os.path.exists(fp) else {}
            d["_status"] = {"airport": airport, "running": False, "error": f"{type(e).__name__}: {e}"}
            _R._atomic_write(fp, d)            # atomic; never race a half-written candidates file
        except Exception:
            pass
    finally:
        with _lock:
            _pending.discard(airport)


def _worker():
    while True:
        airport, n = _jobs.get()
        _run_airport(airport, n)
        _jobs.task_done()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def _authorised(self):
        """True when no password is configured (dev) or the request carries the shared password.
        Username is ignored; only the password is compared, in constant time."""
        if not ACCESS_PASSWORD:
            return True
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Basic "):
            try:
                raw = base64.b64decode(hdr[6:].strip()).decode("utf-8", "replace")
            except Exception:
                return False
            pw = raw.partition(":")[2]
            return hmac.compare_digest(pw, ACCESS_PASSWORD)
        return False

    def _deny(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_HEAD(self):
        if not self._authorised():
            return self._deny()
        return super().do_HEAD()

    def do_GET(self):
        if not self._authorised():
            return self._deny()
        if self.path.startswith("/api/bum"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ap = (q.get("airport", [""])[0] or "").strip().upper()
            if not _AP_RE.match(ap):
                return self._json({"started": False, "error": "airport must be a 3-letter IATA code"}, 400)
            try:
                n = int(q.get("n", ["10"])[0])
            except ValueError:
                return self._json({"started": False, "error": "n must be an integer"}, 400)
            n = max(1, min(MAX_N, n))
            with _lock:
                busy = ap in _pending
                if not busy:
                    _pending.add(ap)
                    _jobs.put((ap, n))
            return self._json({"started": not busy, "busy": busy, "airport": ap, "n": n,
                               "queued": _jobs.qsize()})
        return super().do_GET()

    def do_POST(self):
        if not self._authorised():
            return self._deny()
        if self.path.startswith("/api/zagreb_excel"):
            try:
                import tempfile, subprocess, sys, os as _os
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                td = tempfile.mkdtemp()
                pk = _os.path.join(td, "pack.json")
                outx = _os.path.join(td, "Zagreb Forecast Model (Avia engine).xlsx")
                with open(pk, "wb") as fh:
                    fh.write(body)
                script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "zagreb_write_excel.py")
                r = subprocess.run([sys.executable, script, pk, outx], capture_output=True, text=True, timeout=180)
                if r.returncode != 0 or not _os.path.exists(outx):
                    return self._json({"error": (r.stderr or "build failed")[-800:]}, 500)
                data = open(outx, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", 'attachment; filename="Zagreb Forecast Model (Avia engine).xlsx"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            return
        if self.path.startswith("/api/zagreb_report"):
            try:
                import tempfile, subprocess, sys, os as _os
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                td = tempfile.mkdtemp()
                pk = _os.path.join(td, "pack.json")
                outd = _os.path.join(td, "Zagreb Traffic Forecast - Executive Summary and Assumptions.docx")
                with open(pk, "wb") as fh:
                    fh.write(body)
                script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "zagreb_write_report.py")
                r = subprocess.run([sys.executable, script, pk, outd], capture_output=True, text=True, timeout=180)
                if r.returncode != 0 or not _os.path.exists(outd):
                    return self._json({"error": (r.stderr or "report build failed")[-800:]}, 500)
                data = open(outd, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                self.send_header("Content-Disposition", 'attachment; filename="Zagreb Traffic Forecast - Executive Summary and Assumptions.docx"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                return self._json({"error": str(e)}, 500)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = False   # fail loudly if the port is already held, do not shadow another server


def main():
    os.chdir(ROOT)
    threading.Thread(target=_worker, daemon=True).start()   # one serialised runner
    try:
        httpd = ThreadingServer(("", PORT), Handler)
    except OSError as e:
        print(f"\nCANNOT START: port {PORT} is already in use ({e}).")
        print("Another server (an old serve.py or a previous qsi_service.py) is still running on this port,")
        print("and it is the one answering - which is why no password is being asked.")
        print("Close every other server window, then free the port and start this one again:")
        print(f"    netstat -ano | findstr :{PORT}      (note the PID in the last column)")
        print("    taskkill /PID <pid> /F               (repeat for each PID listed)")
        sys.exit(1)
    with httpd:
        url = f"http://localhost:{PORT}/"
        print(f"Avia Cortex server + QSI route service at {url}")
        print(f"  QSI tool: {QSI_APP}\n  OAG: {QSI_OAG}\n  Sabre: {QSI_SABRE}")
        print("  cockpit -> GET /api/bum?airport=SOU triggers the real optimiser here on the box")
        if ACCESS_PASSWORD:
            print("  access: shared password ON (HTTP Basic Auth) - guests type the password, no account needed")
        else:
            print("  access: NO PASSWORD SET - server is OPEN. Set FORECAST_PASSWORD or webapp/access_password.txt before exposing it over the tunnel.")
        try:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
