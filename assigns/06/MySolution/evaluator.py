"""The single shared evaluator (QLT-02): one entry point, `evaluate`, that
accepts either a source AST node (from lambda1_vp.py, unmodified) or a
target Term (from target_ast.py).

* The source path implements the extended LAMBDA semantics of Section 3.2:
  left-to-right call-by-value with a lexical environment of closures. It is
  a self-contained implementation written for this project -- it does NOT
  call lambda1_vp.EvaluateVisitor (which doesn't support this project's
  "and"/"or"/"not"/comparison operators anyway), so there is exactly one
  evaluator, not two (per "do not implement or delegate to a separate
  source evaluator").
* The target path implements weak, left-to-right call-by-value
  beta-value reduction by capture-avoiding substitution, under a
  configurable, non-negative step budget (RED-01..RED-05). It performs no
  source-language operations and recognizes no Church encodings; it is
  pure term rewriting (ENC-04, RED-05).

This module never imports compiler.py (QLT-02: the evaluator must not
invoke compilation).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional, Union

# `substitute`/`free_vars` (target_ast.py) and the source-language
# evaluator below are structurally recursive over term/expression depth
# (not over the number of beta-value steps, which `_reduce` below handles
# iteratively). A generous recursion limit is just a safety margin for
# large generated terms (e.g. big Church numerals); it is not load-bearing
# for the required demonstrations.
if sys.getrecursionlimit() < 20_000:
    sys.setrecursionlimit(20_000)

# Make the unmodified Assignment 5 source importable regardless of the
# working directory the demo/tests are run from: it lives at
# assigns/05/lambda1_vp.py, i.e. ../../05 relative to this file
# (this file is assigns/06/MySolution/evaluator.py).
_ASSIGN05_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05")
if _ASSIGN05_DIR not in sys.path:
    sys.path.insert(0, _ASSIGN05_DIR)

import lambda1_vp as src
from target_ast import Term, Var, Lam, App, free_vars, substitute


class EvalError(Exception):
    """Raised for a source- or target-evaluation error (unbound variable,
    a type mismatch such as applying a non-function, an open target term,
    or an unsupported/negative source form encountered at evaluation
    time)."""


# ---------------------------------------------------------------------
# Source-language semantic values and environment
# ---------------------------------------------------------------------

class SourceValue:
    """Base class of source-language runtime values."""


@dataclass(frozen=True)
class SInt(SourceValue):
    n: int


@dataclass(frozen=True)
class SBool(SourceValue):
    b: bool


@dataclass(frozen=True)
class SPair(SourceValue):
    first: SourceValue
    second: SourceValue


@dataclass(frozen=True)
class SClosure(SourceValue):
    env: "Env"
    lam: "src.D0Elam"


@dataclass(frozen=True)
class SRecClosure(SourceValue):
    env: "Env"
    fix: "src.D0Efix"


class Env:
    """Base class of the persistent (immutable) lexical environment."""


@dataclass(frozen=True)
class EnvNil(Env):
    pass


@dataclass(frozen=True)
class EnvCons(Env):
    name: str
    value: SourceValue
    rest: "Env"


def env_lookup(env: Env, name: str) -> SourceValue:
    while isinstance(env, EnvCons):
        if env.name == name:
            return env.value
        env = env.rest
    raise EvalError(f"unbound variable: {name!r}")


_SOURCE_BINOPS = ("+", "-", "*", "<", "<=", ">", ">=", "==", "!=")


def eval_source(dexp: "src.d0exp", env: Optional[Env] = None) -> SourceValue:
    """Evaluate a source AST node under left-to-right call-by-value."""
    if env is None:
        env = EnvNil()

    if isinstance(dexp, src.D0Eint):
        if dexp.arg1 < 0:
            raise EvalError(f"negative literal in source evaluation: {dexp.arg1}")
        return SInt(dexp.arg1)

    if isinstance(dexp, src.D0Ebtf):
        return SBool(dexp.arg1)

    if isinstance(dexp, src.D0Evar):
        return env_lookup(env, dexp.arg1)

    if isinstance(dexp, src.D0Elam):
        return SClosure(env, dexp)

    if isinstance(dexp, src.D0Efix):
        return SRecClosure(env, dexp)

    if isinstance(dexp, src.D0Eapp):
        fn = eval_source(dexp.arg1, env)
        arg = eval_source(dexp.arg2, env)
        return _apply_source(fn, arg)

    if isinstance(dexp, src.D0Eif0):
        cond = eval_source(dexp.arg1, env)
        if not isinstance(cond, SBool):
            raise EvalError(f"D0Eif0 condition is not boolean: {cond!r}")
        branch = dexp.arg2 if cond.b else dexp.arg3
        return eval_source(branch, env)

    if isinstance(dexp, src.D0Elet):
        value = eval_source(dexp.arg2, env)
        return eval_source(dexp.arg3, EnvCons(dexp.arg1, value, env))

    if isinstance(dexp, src.D0Epair):
        first = eval_source(dexp.arg1, env)
        second = eval_source(dexp.arg2, env)
        return SPair(first, second)

    if isinstance(dexp, src.D0Epfst):
        p = eval_source(dexp.arg1, env)
        if not isinstance(p, SPair):
            raise EvalError(f"fst of a non-pair: {p!r}")
        return p.first

    if isinstance(dexp, src.D0Epsnd):
        p = eval_source(dexp.arg1, env)
        if not isinstance(p, SPair):
            raise EvalError(f"snd of a non-pair: {p!r}")
        return p.second

    if isinstance(dexp, src.D0Eop1):
        if dexp.name != "not":
            raise EvalError(f"unsupported unary operator: {dexp.name!r}")
        v = eval_source(dexp.arg1, env)
        if not isinstance(v, SBool):
            raise EvalError(f"'not' applied to a non-boolean: {v!r}")
        return SBool(not v.b)

    if isinstance(dexp, src.D0Eop2):
        name = dexp.name
        if name == "and":
            left = eval_source(dexp.arg1, env)
            if not isinstance(left, SBool):
                raise EvalError(f"'and' left operand is not boolean: {left!r}")
            if not left.b:
                return SBool(False)
            right = eval_source(dexp.arg2, env)
            if not isinstance(right, SBool):
                raise EvalError(f"'and' right operand is not boolean: {right!r}")
            return right
        if name == "or":
            left = eval_source(dexp.arg1, env)
            if not isinstance(left, SBool):
                raise EvalError(f"'or' left operand is not boolean: {left!r}")
            if left.b:
                return SBool(True)
            right = eval_source(dexp.arg2, env)
            if not isinstance(right, SBool):
                raise EvalError(f"'or' right operand is not boolean: {right!r}")
            return right
        if name not in _SOURCE_BINOPS:
            raise EvalError(f"unsupported binary operator: {name!r}")
        left = eval_source(dexp.arg1, env)
        right = eval_source(dexp.arg2, env)
        if not isinstance(left, SInt) or not isinstance(right, SInt):
            raise EvalError(f"{name!r} applied to non-naturals: {left!r}, {right!r}")
        if name == "+":
            return SInt(left.n + right.n)
        if name == "-":
            return SInt(max(left.n - right.n, 0))
        if name == "*":
            return SInt(left.n * right.n)
        if name == "<":
            return SBool(left.n < right.n)
        if name == "<=":
            return SBool(left.n <= right.n)
        if name == ">":
            return SBool(left.n > right.n)
        if name == ">=":
            return SBool(left.n >= right.n)
        if name == "==":
            return SBool(left.n == right.n)
        if name == "!=":
            return SBool(left.n != right.n)

    raise EvalError(f"unsupported source expression: {dexp!r}")


def _apply_source(fn: SourceValue, arg: SourceValue) -> SourceValue:
    if isinstance(fn, SClosure):
        lam = fn.lam
        return eval_source(lam.arg2, EnvCons(lam.arg1, arg, fn.env))
    if isinstance(fn, SRecClosure):
        fx = fn.fix
        env1 = EnvCons(fx.arg1, fn, fn.env)  # function name bound to the closure
        env2 = EnvCons(fx.arg2, arg, env1)   # parameter; shadows fn name if coincident
        return eval_source(fx.arg3, env2)
    raise EvalError(f"applying a non-function value: {fn!r}")


# ---------------------------------------------------------------------
# Target-language (pure lambda calculus) weak CBV reduction
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TargetResult:
    status: str  # "completed" or "exhausted"
    term: Term   # the resulting value if completed; the not-yet-reduced
                 # redex-in-context if exhausted
    steps: int   # number of beta-value steps actually performed


class _Exhausted(Exception):
    def __init__(self, partial: Term, steps: int):
        self.partial = partial
        self.steps = steps


def eval_target(term: Term, budget: int) -> TargetResult:
    """Weak, left-to-right call-by-value reduction of a closed target term,
    under a non-negative beta-value step budget (RED-01..RED-04).

    Execution is restricted to closed terms (RED-02): an open term is
    rejected immediately with EvalError, rather than silently evaluated.
    """
    if budget < 0:
        raise ValueError("step budget must be nonnegative")
    free = free_vars(term)
    if free:
        raise EvalError(
            f"cannot execute an open target term; free variables: {sorted(free)}"
        )
    counter = [0]
    try:
        value = _reduce(term, budget, counter)
        return TargetResult("completed", value, counter[0])
    except _Exhausted as exc:
        return TargetResult("exhausted", exc.partial, exc.steps)


def _reduce(term: Term, budget: int, counter: list[int]) -> Term:
    """Reduce `term` to a value (a Lam), or raise _Exhausted if the budget
    runs out first. Never reduces beneath a lambda (no eta, no reduction
    under binders): a Lam is always already a value, in zero steps.

    Implemented as an explicit stack machine rather than direct Python
    recursion: a real reduction (e.g. recursive factorial or Fibonacci on
    even modest inputs) performs hundreds to thousands of chained
    beta-value steps, and chaining that many recursive calls would exceed
    Python's call-stack depth. The two frame kinds on the explicit stack
    are exactly the two things weak left-to-right call-by-value can be
    "in the middle of": having evaluated an application's function and
    now needing to evaluate its argument (EVAL_ARG), or having evaluated
    both and now needing to perform the beta step (APPLY).
    """
    EVAL_ARG, APPLY = 0, 1
    stack: list[tuple[int, object]] = []
    current: Term = term

    while True:
        if isinstance(current, Var):
            # Cannot happen for a term that started closed, since
            # substitution is capture-safe and eval_target already
            # rejected top-level open input; kept as a defensive check.
            raise EvalError(
                f"encountered a free variable during reduction: {current.name!r}"
            )

        if isinstance(current, App):
            stack.append((EVAL_ARG, current.arg))
            current = current.fn
            continue

        if isinstance(current, Lam):
            value = current
            if not stack:
                return value
            kind, payload = stack.pop()
            if kind == EVAL_ARG:
                stack.append((APPLY, value))
                current = payload  # now evaluate the argument
                continue
            else:  # APPLY
                fn_val = payload
                arg_val = value
                if not isinstance(fn_val, Lam):
                    raise EvalError(
                        f"applying a non-function target value: {fn_val!r}"
                    )
                if counter[0] >= budget:
                    raise _Exhausted(App(fn_val, arg_val), counter[0])
                counter[0] += 1
                current = substitute(fn_val.body, fn_val.name, arg_val)
                continue

        raise TypeError(f"not a Term: {current!r}")


# ---------------------------------------------------------------------
# The single shared entry point
# ---------------------------------------------------------------------

def evaluate(
    node: Union["src.d0exp", Term],
    *,
    env: Optional[Env] = None,
    budget: Optional[int] = None,
):
    """Evaluate either a source AST node or a target Term.

    - For a target Term, `budget` is required and the result is a
      TargetResult (completed/exhausted, value, step count) -- bounded,
      per RED-03/RED-04.
    - For a source AST node, evaluation is unbounded (per the assignment,
      source-side evaluation need not be step-bounded) and the result is
      a SourceValue.
    """
    if isinstance(node, Term):
        if budget is None:
            raise ValueError("evaluating a target term requires a step budget")
        return eval_target(node, budget)
    if isinstance(node, src.D0E000):
        return eval_source(node, env if env is not None else EnvNil())
    raise TypeError(f"not a source or target expression: {node!r}")
