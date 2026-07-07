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

Config (defaults suit John's machine; override with env vars):
    QSI_APP    = ...\\Avia QSI Tool\\app   (env override; default is the OneDrive Projects path)
    QSI_OAG    = C:\\Avia\\oag.duckdb
    QSI_SABRE  = C:\\Avia\\sabre.duckdb
Run:  set PORT=8000 & python qsi_service.py      (then expose via the tunnel, as for the QSI tool)
"""
import http.server, socketserver, threading, queue, re, os, sys, json, urllib.parse, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(ROOT), "scripts")
sys.path.insert(0, SCRIPTS)
PORT = int(os.environ.get("PORT", "8000"))
QSI_APP = os.environ.get("QSI_APP", r"C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia QSI Tool\app")
QSI_OAG = os.environ.get("QSI_OAG", r"C:\Avia\oag.duckdb")
QSI_SABRE = os.environ.get("QSI_SABRE", r"C:\Avia\sabre.duckdb")

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

    def do_GET(self):
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

    def log_message(self, *a):
        pass


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    os.chdir(ROOT)
    threading.Thread(target=_worker, daemon=True).start()   # one serialised runner
    with ThreadingServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"Avia Cortex server + QSI route service at {url}")
        print(f"  QSI tool: {QSI_APP}\n  OAG: {QSI_OAG}\n  Sabre: {QSI_SABRE}")
        print("  cockpit -> GET /api/bum?airport=SOU triggers the real optimiser here on the box")
        try:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
