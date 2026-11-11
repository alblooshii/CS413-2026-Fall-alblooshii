"""The four RPC methods: params validation (RPC.md 4.2) and error mapping (5.1).

Does not import lambda3. Work is delegated to `backend(op, source, target)`,
which returns plain outcome data (see lambda_service.execute) or raises
runner.DeadlineExceeded / any other exception.
"""

import logging

from . import jsonrpc
from .jsonrpc import RpcError
from .runner import DEADLINE_SECONDS, DeadlineExceeded

log = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 10_000
TARGETS = ("python", "javascript")


def _invalid(reason, **extra):
    return RpcError(jsonrpc.INVALID_PARAMS, {"reason": reason, **extra})


def _check_source(params):
    if "source" not in params:
        raise _invalid("missing_param", param="source")
    source = params["source"]
    if not isinstance(source, str):
        raise _invalid("wrong_type", param="source")
    if not source.strip():
        raise _invalid("blank", param="source")
    if len(source) > MAX_SOURCE_CHARS:
        raise _invalid("too_long", param="source", max_length=MAX_SOURCE_CHARS)
    try:
        source.encode("utf-8")
    except UnicodeEncodeError:  # lone surrogate from a "\ud800" escape
        raise _invalid("invalid_unicode", param="source") from None
    return source


def _check_target(params):
    if "target" not in params:
        raise _invalid("missing_param", param="target")
    target = params["target"]
    if not isinstance(target, str):
        raise _invalid("wrong_type", param="target")
    if target not in TARGETS:
        raise _invalid("invalid_value", param="target", allowed=list(TARGETS))
    return target


def _check_params(params, allowed):
    if not isinstance(params, dict):
        raise _invalid("params_must_be_object")
    source = _check_source(params) if "source" in allowed else None
    target = _check_target(params) if "target" in allowed else None
    for name in params:
        if name not in allowed:
            raise _invalid("unexpected_param", param=name)
    return source, target


def _unwrap(outcome):
    """Turn a backend outcome into a result, or the matching RpcError."""
    if outcome["ok"]:
        return outcome["result"]
    failure = outcome["failure"]
    kind = failure["kind"]
    if kind == "syntax_error":
        raise RpcError(jsonrpc.LAMBDA_SYNTAX_ERROR, failure)
    if kind == "type_error":
        raise RpcError(jsonrpc.LAMBDA_TYPE_ERROR, failure)
    if kind == "internal":
        log.error("worker failed:\n%s", failure.get("log", "(no log)"))
        raise RpcError(jsonrpc.INTERNAL_ERROR)
    raise RpcError(jsonrpc.LAMBDA_RUNTIME_ERROR, {"kind": kind})


def build_methods(backend):
    """Return the {method name: handler(params) -> result} table."""

    def health(params):
        _check_params(params, allowed=())
        return {"status": "ok", "version": "1.0"}

    def source_method(op, allowed):
        def handler(params):
            source, target = _check_params(params, allowed)
            try:
                outcome = backend(op, source, target)
            except DeadlineExceeded:
                raise RpcError(jsonrpc.EXECUTION_TIMEOUT,
                               {"kind": "timeout", "limit_seconds": DEADLINE_SECONDS}) from None
            return _unwrap(outcome)
        return handler

    return {
        "service.health": health,
        "lambda.typecheck": source_method("typecheck", ("source",)),
        "lambda.interpret": source_method("interpret", ("source",)),
        "lambda.compile": source_method("compile", ("source", "target")),
    }
