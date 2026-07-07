"""Avia Global Aviation Forecast - local viewer. Zero-dependency (Python stdlib only).
Run:  python serve.py         then open http://localhost:8000
Serves the dashboard and the engine data bundle in ./data. Author: Avia Solutions."""
import http.server, socketserver, os, webbrowser, threading

PORT = int(os.environ.get("PORT", "8000"))
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
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"Avia Global Forecast viewer running at {url}  (Ctrl+C to stop)")
        try:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
