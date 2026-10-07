"""HTTP binding (composition root): routes -> Controller -> View.

Each route only translates an HTTP request into one controller call and
returns ``view.present(...)`` as JSON. No state rules or language logic here.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .backend import Lambda1Backend
from .controller import Controller, Notice
from .model import MAX_SOURCE_BYTES, AppModel
from .view import present

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
CANNED_FILES = {
    "factorial": ("Factorial (canned)", "factorial.txt"),
    "fibonacci": ("Fibonacci (canned)", "fibonacci.txt"),
}


def load_canned(samples_dir: Path = SAMPLES_DIR) -> dict[str, tuple[str, str]]:
    return {key: (name, (samples_dir / fname).read_text(encoding="utf-8"))
            for key, (name, fname) in CANNED_FILES.items()}


def create_app(controller: Controller | None = None) -> Flask:
    if controller is None:
        controller = Controller(AppModel(), Lambda1Backend(), load_canned())
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4 * MAX_SOURCE_BYTES

    def reply(notice: Notice | None = None):
        body = present(controller.state(), notice)
        status = 200 if notice is None or notice.ok else 409
        return jsonify(body), status

    @app.after_request
    def security_headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(413)
    def too_large(_):
        return reply(Notice(False, f"File exceeds the {MAX_SOURCE_BYTES}-byte "
                                   "limit.", "too_large"))

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def state():
        return reply()

    @app.post("/api/load/canned")
    def load_canned_route():
        key = (request.get_json(silent=True) or {}).get("key", "")
        return reply(controller.load_canned(key))

    @app.post("/api/load/file")
    def load_file():
        up = request.files.get("file")
        if up is None:
            return reply(Notice(False, "No file was received.", "no_file"))
        raw = up.stream.read(MAX_SOURCE_BYTES + 1)
        return reply(controller.load_upload(up.filename or "", raw))

    @app.post("/api/load/manual")
    def load_manual():
        return reply(controller.open_manual())

    @app.put("/api/draft")
    def draft():
        text = (request.get_json(silent=True) or {}).get("text", "")
        return reply(controller.edit(str(text)))

    @app.post("/api/apply")
    def apply():
        text = (request.get_json(silent=True) or {}).get("text")
        return reply(controller.apply(None if text is None else str(text)))

    @app.post("/api/discard")
    def discard():
        return reply(controller.discard())

    @app.post("/api/action/<name>")
    def action(name: str):
        return reply(controller.run(name))

    return app
