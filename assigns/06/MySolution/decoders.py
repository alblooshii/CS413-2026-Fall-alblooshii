"""Task 4: bounded observers that decode a target value back into a Python
answer, using only pure target-syntax observation contexts evaluated by
the same call-by-value engine (OBS-01..OBS-03). Python inspects final,
already-reduced observation *shapes* -- it never executes generated
arithmetic, never reduces under lambdas, and never recognizes a Church
encoding mid-reduction to substitute a host computation (ENC-04, RED-05).

Two observation contexts, both pure target terms:

    STEP = lam tail. lam c. lam z. c tail
    BASE = lam c. lam z. z

    natural-number observation:  n STEP BASE
    boolean observation:         b MARK_A MARK_B   (two distinct closed
                                                      marker values)

A caller must supply the *expected kind* (nat/bool/pair of kinds), because
NUM(0) and FALSE share the same lambda representation and cannot be told
apart by shape alone (see Task 4 of Assign06).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from target_ast import Term, Var, Lam, App, alpha_equivalent
from evaluator import eval_target
import church as C


# ---------------------------------------------------------------------
# Observation contexts
# ---------------------------------------------------------------------

def _step_context() -> Term:
    return Lam("tail", Lam("c", Lam("z", App(Var("c"), Var("tail")))))


def _base_context() -> Term:
    return Lam("c", Lam("z", Var("z")))


def _marker_a() -> Term:
    # Reuse the TRUE/FALSE shapes themselves as the two distinct closed
    # markers: a genuine Church boolean b decodes correctly because
    # `b MARK_A MARK_B` is exactly `b TRUE FALSE`, which selects MARK_A for
    # TRUE and MARK_B for FALSE by definition. Unlike a pair of markers
    # built from the identity combinator (which an iterated, non-boolean
    # value such as a Church numeral can trivially collapse into,
    # producing a false "ok" decode), a value that is not a genuine
    # 2-argument boolean selector generally yields a term of the wrong
    # shape here and is correctly reported as malformed instead.
    return C.TRUE()


def _marker_b() -> Term:
    return C.FALSE()


# ---------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ObserveResult:
    status: str          # "ok" | "exhausted" | "malformed"
    value: object         # decoded Python value when status == "ok"; else None
    steps: int             # beta-value steps used by this observation step
                             # (does not include the "execution" budget used
                             # to reduce the program to a value beforehand --
                             # that is accounted for separately, see
                             # observe_value / DEM-02 / "document separate
                             # execution and observation budgets").


# ---------------------------------------------------------------------
# Natural-number observer
# ---------------------------------------------------------------------

def observe_nat(value_term: Term, obs_budget: int) -> ObserveResult:
    """Decode a target *value* (already reduced to a lambda) expected to
    represent a Church natural, under an observation-step budget."""
    probe = App(App(value_term, _step_context()), _base_context())
    result = eval_target(probe, obs_budget)
    if result.status == "exhausted":
        return ObserveResult("exhausted", None, result.steps)
    n = _count_nat_spine(result.term)
    if n is None:
        return ObserveResult("malformed", None, result.steps)
    return ObserveResult("ok", n, result.steps)


def _count_nat_spine(term: Term):
    """Structurally count a (possibly alpha-renamed) Church-numeral spine
    of the shape produced by applying a numeral to STEP and BASE. Returns
    None if the shape does not match (malformed observation output)."""
    count = 0
    t = term
    while True:
        if not isinstance(t, Lam):
            return None
        c_name = t.name
        inner = t.body
        if not isinstance(inner, Lam):
            return None
        z_name = inner.name
        body = inner.body
        if isinstance(body, Var) and body.name == z_name:
            return count
        if isinstance(body, App) and isinstance(body.fn, Var) and body.fn.name == c_name:
            count += 1
            t = body.arg
            continue
        return None


# ---------------------------------------------------------------------
# Boolean observer
# ---------------------------------------------------------------------

def observe_bool(value_term: Term, obs_budget: int) -> ObserveResult:
    """Decode a target value expected to represent a Church boolean."""
    mark_a, mark_b = _marker_a(), _marker_b()
    probe = App(App(value_term, mark_a), mark_b)
    result = eval_target(probe, obs_budget)
    if result.status == "exhausted":
        return ObserveResult("exhausted", None, result.steps)
    if alpha_equivalent(result.term, mark_a):
        return ObserveResult("ok", True, result.steps)
    if alpha_equivalent(result.term, mark_b):
        return ObserveResult("ok", False, result.steps)
    return ObserveResult("malformed", None, result.steps)


# ---------------------------------------------------------------------
# Kinds, used to drive (possibly nested) pair observation
# ---------------------------------------------------------------------

NAT = "nat"
BOOL = "bool"


def PAIR_KIND(first_kind, second_kind):
    return ("pair", first_kind, second_kind)


def observe_value(
    term: Term,
    kind,
    *,
    exec_budget: int,
    obs_budget: int,
) -> ObserveResult:
    """Full observation pipeline (OBS-02, OBS-03): first reduce `term` to a
    value under `exec_budget` beta-value steps (this is the *execution*
    budget -- reducing the compiled program itself, or a projection of a
    pair, to a value); then decode that value per `kind` under
    `obs_budget` further beta-value steps (the *observation* budget,
    spent on STEP/BASE or marker probes, and on evaluating a pair's
    projections). `kind` is NAT, BOOL, or PAIR_KIND(k1, k2) for a
    (possibly nested) pair. Steps reported are the sum of whatever
    observation-stage reductions were performed at this call (pair
    observation recurses, accumulating steps from nested calls); the
    caller is expected to report the execution-stage step count
    separately, from eval_target's own result on `term`.
    """
    exec_result = eval_target(term, exec_budget)
    if exec_result.status == "exhausted":
        return ObserveResult("exhausted", None, exec_result.steps)
    value = exec_result.term

    if kind == NAT:
        return observe_nat(value, obs_budget)
    if kind == BOOL:
        return observe_bool(value, obs_budget)
    if isinstance(kind, tuple) and len(kind) == 3 and kind[0] == "pair":
        _, k1, k2 = kind
        fst_term = App(C.FST(), value)
        snd_term = App(C.SND(), value)
        r1 = observe_value(fst_term, k1, exec_budget=exec_budget, obs_budget=obs_budget)
        if r1.status != "ok":
            return r1
        r2 = observe_value(snd_term, k2, exec_budget=exec_budget, obs_budget=obs_budget)
        if r2.status != "ok":
            return r2
        return ObserveResult("ok", (r1.value, r2.value), r1.steps + r2.steps)
    return ObserveResult("malformed", None, 0)
