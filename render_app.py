from __future__ import annotations

from pathlib import Path
from flask import Flask, send_from_directory, Response

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(ROOT / "assets"))


@app.route("/")
def index() -> Response:
    return send_from_directory(str(ROOT), "index.html")


@app.route("/manual_usuario.html")
def manual():
    return send_from_directory(str(ROOT), "manual_usuario.html")


@app.route("/assets/<path:filename>")
def assets(filename: str):
    return send_from_directory(str(ROOT / "assets"), filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
