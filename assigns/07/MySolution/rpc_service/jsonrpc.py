"""JSON-RPC 2.0 envelope layer (RPC.md sections 2, 3 and 5).

Knows nothing about LAMBDA3 or HTTP. `handle_body` turns raw request bytes and
a {method name: handler} table into (http_status, payload) where status is 200
(payload is a response object or list) or 204 (payload is None).
"""

import json
import logging
import math

log = logging.getLogger(__name__)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
LAMBDA_SYNTAX_ERROR = -32010
LAMBDA_TYPE_ERROR = -32011
EXECUTION_TIMEOUT = -32012
LAMBDA_RUNTIME_ERROR = -32013

MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    LAMBDA_SYNTAX_ERROR: "LAMBDA syntax error",
    LAMBDA_TYPE_ERROR: "LAMBDA type error",
    EXECUTION_TIMEOUT: "Execution timeout",
    LAMBDA_RUNTIME_ERROR: "LAMBDA runtime error",
}

MAX_BATCH = 10


class RpcError(Exception):
    """Raised by a method handler to produce a JSON-RPC error response."""

    def __init__(self, code, data=None):
        super().__init__(MESSAGES[code])
        self.code = code
        self.data = data


def error_response(request_id, code, data=None):
    error = {"code": code, "message": MESSAGES[code]}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _reject_constant(name):
    raise ValueError(f"non-standard JSON constant {name}")


def _invalid_reason(item):
    """Return None for a valid request object, else the RPC.md reason string."""
    if not isinstance(item, dict):
        return "not_an_object"
    if item.get("jsonrpc") != "2.0":
        return "bad_jsonrpc_version"
    if not isinstance(item.get("method"), str):
        return "bad_method"
    if "id" in item:
        rid = item["id"]
        if isinstance(rid, bool) or not (
            rid is None or isinstance(rid, (str, int))
            or (isinstance(rid, float) and math.isfinite(rid))
        ):
            return "bad_id"
    if "params" in item and not isinstance(item["params"], (dict, list)):
        return "bad_params_type"
    return None


def _execute(request, methods):
    """Run a valid request; return its result or raise RpcError / anything else."""
    handler = methods.get(request["method"])
    if handler is None:
        raise RpcError(METHOD_NOT_FOUND)
    return handler(request.get("params", {}))


def _handle_item(item, methods):
    """Return a response object, or None for a valid notification."""
    reason = _invalid_reason(item)
    if reason:
        return error_response(None, INVALID_REQUEST, {"reason": reason})

    is_call = "id" in item
    try:
        result = _execute(item, methods)
    except RpcError as exc:
        response = error_response(item.get("id"), exc.code, exc.data)
    except Exception:  # noqa: BLE001 - the boundary: never leak details
        log.exception("unexpected failure handling method %r", item["method"])
        response = error_response(item.get("id"), INTERNAL_ERROR)
    else:
        response = {"jsonrpc": "2.0", "id": item.get("id"), "result": result}

    if is_call:
        return response
    if "error" in response:  # notifications never report errors to the client
        log.info("notification %r failed with code %s", item["method"], response["error"]["code"])
    return None


def handle_body(raw, methods):
    """Process a request body. Returns (status, payload): 200 + object/list, or 204 + None."""
    try:
        document = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except UnicodeDecodeError:
        return 200, error_response(None, PARSE_ERROR, {"reason": "invalid_utf8"})
    except (ValueError, RecursionError):
        return 200, error_response(None, PARSE_ERROR, {"reason": "invalid_json"})

    if isinstance(document, list):
        if not document:
            return 200, error_response(None, INVALID_REQUEST, {"reason": "empty_batch"})
        if len(document) > MAX_BATCH:
            return 200, error_response(None, INVALID_REQUEST, {"reason": "batch_too_large"})
        responses = [r for r in (_handle_item(i, methods) for i in document) if r is not None]
        return (200, responses) if responses else (204, None)

    response = _handle_item(document, methods)
    return (200, response) if response is not None else (204, None)
