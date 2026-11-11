"""Service adapter: the only module that imports lambda3.

`execute` runs one operation and returns plain data (never exceptions), so it
can cross a process boundary. It contains no parsing, type-checking,
interpreting or compiling logic of its own; it only calls lambda3 and
classifies what lambda3 raises. Generated code is returned as text and is
never executed.
"""

import contextlib
import io
import os
import sys
from pathlib import Path

# <assign dir>/LAMBDA3 sits next to MySolution/; LAMBDA3_DIR overrides it.
_LAMBDA_DIR = os.environ.get("LAMBDA3_DIR") or str(Path(__file__).resolve().parents[2] / "LAMBDA3")
sys.path.insert(0, _LAMBDA_DIR)
import lambda3 as L  # noqa: E402

sys.set_int_max_str_digits(0)  # big factorials must format; the deadline bounds the cost

OPERATIONS = ("typecheck", "interpret", "compile")

# Python exception -> RPC.md section 5.3 kind (RecursionError can strike in any stage).
_RUNTIME_KINDS = (
    (ZeroDivisionError, "division_by_zero"),
    (RecursionError, "recursion_limit"),
    (IndexError, "index_out_of_range"),
    (ValueError, "invalid_operation"),
    (MemoryError, "memory_limit"),
)


def _runtime_kind(exc, evaluating):
    for exc_type, kind in _RUNTIME_KINDS:
        if isinstance(exc, exc_type) and (evaluating or isinstance(exc, (RecursionError, MemoryError))):
            return kind
    return None


def _failure(**fields):
    return {"ok": False, "failure": fields}


def execute(op, source, target=None):
    """Run `op` on `source`. Returns {"ok": True, "result": {...}} or {"ok": False, "failure": {...}}."""
    evaluating = False
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # LAMBDA print(...) output is discarded
            expr, typ = L.d0exp_parse_and_typecheck(source)
            if op == "typecheck":
                return {"ok": True, "result": {"type": L.format_type(typ)}}
            if op == "interpret":
                evaluating = True
                value = L.d0exp_evaluate(expr)
                return {"ok": True, "result": {"type": L.format_type(typ), "value": L.d0val_format(value)}}
            code = L.d0exp_compile(expr) if target == "python" else L.d0exp_compile_js(expr)
            return {"ok": True, "result": {"target": target, "code": code}}
    except L.LambdaSyntaxError as exc:  # subclass of SyntaxError
        return _failure(kind="syntax_error", detail=exc.msg, line=exc.lineno, column=exc.offset, text=exc.text)
    except L.TypeCheckError as exc:  # subclass of TypeError: must not be caught as one
        return _failure(kind="type_error", detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        kind = _runtime_kind(exc, evaluating)
        if kind:
            return _failure(kind=kind)
        raise
