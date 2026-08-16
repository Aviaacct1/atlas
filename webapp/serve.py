"""Avia Global Forecast - LOCAL PREVIEW ONLY. Zero-dependency (Python stdlib only).
Run:  python serve.py         then open http://localhost:8000

This server has NO authentication, so since 16 August 2026 it binds 127.0.0.1 only:
the tunnel and the LAN cannot reach it. Serving to anyone else goes through
qsi_service.py, which fails closed without a password. Author: Avia Solutions."""
import http.server, socketserver, os, webbrowser, threading

PORT = int(os.environ.get("PORT", "8000"))
BIND = "127.0.0.1"   # loopback only, deliberately not configurable: this file has no auth
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def main():
    os.chdir(ROOT)
    with socketserver.TCPServer((BIND, PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"Avia Global Forecast local preview at {url}  (loopback only, no auth; Ctrl+C to stop)")
        try:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
