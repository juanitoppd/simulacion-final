from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer


ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("PORT", "8000"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)


if __name__ == "__main__":
    with TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving {ROOT} on port {PORT}")
        httpd.serve_forever()
