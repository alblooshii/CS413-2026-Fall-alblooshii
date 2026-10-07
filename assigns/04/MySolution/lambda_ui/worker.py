"""Worker process: runs ONE language operation and prints a JSON result.

Started by ``backend.Lambda1Backend`` in a separate interpreter so that a
nonterminating or crashing program can be killed after a timeout without
affecting the web server. Protocol: one JSON object on stdin
({"op": "lint"|"interpret", "source": "..."}), one JSON object on stdout
({"outcome": ..., "message": ...}).
"""
from __future__ import annotations

import json
import sys

import lambda1
from lambda_ui.reader import ReadError, read_d0exp

MAX_OUTPUT_CHARS = 20_000
RECURSION_LIMIT = 6_000


def _contains_error_value(val) -> bool:
    stack = [val]
    while stack:
        v = stack.pop()
        if type(v) is lambda1.D0V000:
            return True
        if isinstance(v, lambda1.D0Vpair):
            stack.extend((v.arg1, v.arg2))
    return False


def lint(text: str) -> dict:
    try:
        exp = read_d0exp(text)
    except ReadError as exc:
        return {"outcome": "input_error", "message": f"Invalid input: {exc}"}
    free = lambda1.d0exp_fvset(exp)          # never evaluates
    if free:
        names = ", ".join(sorted(free))
        return {"outcome": "language_error",
                "message": f"Undeclared variable(s): {names}"}
    return {"outcome": "success", "message": "No free variables found."}


def interpret(text: str) -> dict:
    try:
        exp = read_d0exp(text)
    except ReadError as exc:
        return {"outcome": "input_error", "message": f"Invalid input: {exc}"}
    try:
        val = lambda1.d0exp_evaluate(exp, lambda1.ENVnil())
    except RecursionError:
        return {"outcome": "runtime_error",
                "message": "Runtime error: recursion too deep "
                           "(the program may not terminate)."}
    except Exception as exc:                  # noqa: BLE001 - report anything
        return {"outcome": "runtime_error",
                "message": f"Runtime error: {type(exc).__name__}: {exc}"}
    if _contains_error_value(val):
        return {"outcome": "runtime_error",
                "message": "Runtime error: evaluation produced the error "
                           "value D0V000() (for example an unbound variable)."}
    out = repr(val)
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + f"\n... [output truncated at {MAX_OUTPUT_CHARS} characters]"
    return {"outcome": "success", "message": out}


OPS = {"lint": lint, "interpret": interpret}


def main() -> int:
    sys.setrecursionlimit(RECURSION_LIMIT)
    req = json.load(sys.stdin)
    handler = OPS[req["op"]]
    json.dump(handler(req["source"]), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
