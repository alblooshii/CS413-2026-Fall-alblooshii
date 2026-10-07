"""Restricted constructor reader: text -> d0exp, without executing anything.

Accepts a single Python *expression* built only from the d0exp constructors,
int/bool/str literals (and negative int literals). The text is parsed with
``ast.parse(mode="eval")`` and the tree is walked by hand; ``eval``/``exec``
are never used, so uploaded text cannot run arbitrary code.
"""
from __future__ import annotations

import ast

import lambda1

MAX_DEPTH = 200

# constructor name -> (class, field kinds); kinds: int, bool, str, exp
CONSTRUCTORS: dict[str, tuple[type, tuple[str, ...]]] = {
    "D0Eint": (lambda1.D0Eint, ("int",)),
    "D0Ebtf": (lambda1.D0Ebtf, ("bool",)),
    "D0Evar": (lambda1.D0Evar, ("str",)),
    "D0Eop1": (lambda1.D0Eop1, ("str", "exp")),
    "D0Eop2": (lambda1.D0Eop2, ("str", "exp", "exp")),
    "D0Elam": (lambda1.D0Elam, ("str", "exp")),
    "D0Efix": (lambda1.D0Efix, ("str", "str", "exp")),
    "D0Eapp": (lambda1.D0Eapp, ("exp", "exp")),
    "D0Eif0": (lambda1.D0Eif0, ("exp", "exp", "exp")),
    "D0Elet": (lambda1.D0Elet, ("str", "exp", "exp")),
    "D0Epair": (lambda1.D0Epair, ("exp", "exp")),
    "D0Epfst": (lambda1.D0Epfst, ("exp",)),
    "D0Epsnd": (lambda1.D0Epsnd, ("exp",)),
}


class ReadError(Exception):
    """The text is not a valid constructor expression."""


def _where(node: ast.AST) -> str:
    return f" (line {node.lineno})" if hasattr(node, "lineno") else ""


def _field_names(cls: type) -> tuple[str, ...]:
    return tuple(cls.__dataclass_fields__)


def _literal(node: ast.AST, kind: str, ctor: str):
    value = None
    ok = False
    if isinstance(node, ast.Constant):
        value, ok = node.value, True
    elif (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
          and isinstance(node.operand, ast.Constant)
          and type(node.operand.value) is int):
        value, ok = -node.operand.value, True
    if kind == "int" and ok and type(value) is int:
        return value
    if kind == "bool" and ok and type(value) is bool:
        return value
    if kind == "str" and ok and type(value) is str:
        return value
    raise ReadError(f"{ctor}: expected a {kind} literal{_where(node)}")


def _build(node: ast.AST, depth: int):
    if depth > MAX_DEPTH:
        raise ReadError(f"expression is nested deeper than {MAX_DEPTH} levels")
    if not isinstance(node, ast.Call):
        raise ReadError(
            f"expected a constructor call such as D0Eint(1){_where(node)}")
    if not isinstance(node.func, ast.Name):
        raise ReadError(f"only plain constructor names are allowed{_where(node)}")
    name = node.func.id
    if name not in CONSTRUCTORS:
        raise ReadError(f"unknown constructor {name!r}{_where(node)}")
    cls, kinds = CONSTRUCTORS[name]
    args = list(node.args)
    if any(isinstance(a, ast.Starred) for a in args):
        raise ReadError(f"{name}: starred arguments are not allowed{_where(node)}")
    fields = _field_names(cls)
    if len(args) > len(kinds):
        raise ReadError(
            f"{name} takes {len(kinds)} argument(s), got {len(args)}{_where(node)}")
    slots: list[ast.AST | None] = args + [None] * (len(kinds) - len(args))
    for kw in node.keywords:
        if kw.arg is None or kw.arg not in fields:
            raise ReadError(f"{name}: unknown keyword {kw.arg!r}{_where(node)}")
        idx = fields.index(kw.arg)
        if slots[idx] is not None:
            raise ReadError(f"{name}: duplicate argument {kw.arg!r}{_where(node)}")
        slots[idx] = kw.value
    if any(s is None for s in slots):
        raise ReadError(
            f"{name} takes {len(kinds)} argument(s), got "
            f"{sum(s is not None for s in slots)}{_where(node)}")
    values = []
    for arg, kind in zip(slots, kinds):
        values.append(_build(arg, depth + 1) if kind == "exp"
                      else _literal(arg, kind, name))
    return cls(*values)


def read_d0exp(text: str):
    """Parse ``text`` into a d0exp or raise ReadError."""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        where = f" (line {exc.lineno})" if exc.lineno else ""
        raise ReadError(f"syntax error: {exc.msg}{where}") from None
    except (RecursionError, MemoryError):
        raise ReadError("expression is too deeply nested to read") from None
    except ValueError as exc:      # e.g. null bytes
        raise ReadError(f"cannot read source: {exc}") from None
    try:
        return _build(tree.body, 0)
    except RecursionError:
        raise ReadError("expression is too deeply nested to read") from None
