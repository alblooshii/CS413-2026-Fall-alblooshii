"""HTTP transport (RPC.md section 1 and 3.1): POST /rpc, nothing else.

Checks path, verb, body size and media type, then hands the raw bytes to the
JSON-RPC layer. Every JSON-RPC outcome is HTTP 200, or 204 when there is
nothing to send back.
"""

import json

from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException, UnsupportedMediaType

from . import jsonrpc, methods, runner

MAX_BODY_BYTES = 1 << 20  # 1 MiB


def create_app(backend=None):
    """Build the app. `backend` runs one call under a deadline; tests inject doubles."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    table = methods.build_methods(backend or runner.run_with_deadline)

    @app.post("/rpc")
    def rpc():
        raw = request.get_data()  # raises 413 above MAX_BODY_BYTES
        if request.mimetype != "application/json" or \
                request.mimetype_params.get("charset", "utf-8").lower() != "utf-8":
            raise UnsupportedMediaType("Content-Type must be application/json (UTF-8)")
        status, payload = jsonrpc.handle_body(raw, table)
        if payload is None:
            empty = Response(status=status)
            empty.headers.pop("Content-Type")  # no body, so no Content-Type
            return empty
        return Response(json.dumps(payload, allow_nan=False), status=status,
                        content_type="application/json; charset=utf-8")

    @app.errorhandler(HTTPException)
    def transport_error(exc):  # 404 / 405 / 413 / 415: small JSON body, not a JSON-RPC response
        response = exc.get_response()
        response.set_data(json.dumps({"error": exc.name}))
        response.content_type = "application/json"
        return response

    return app
