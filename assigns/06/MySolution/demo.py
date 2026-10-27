"""Task 4 / DEM-01, DEM-02: one documented command that runs all mandatory
examples through compilation, target reduction, and decoding, and reports
source, generated term (or its saved-file location), execution status and
step count, observation status and step count, decoded answer, and the
explicit expected answer -- with execution and observation budgets
reported separately (OBS-03, DEM-02).

Run from assigns/06/:

    python3 MySolution/demo.py

Budgets (documented here and in README.md):

  * EXEC_BUDGET = 200,000 beta-value steps: the budget used to reduce a
    compiled program to a value. The largest terminating demo (recursive
    factorial of 4) measured 746 steps and Fibonacci of 5 measured 1840
    steps during development, so this budget carries roughly a
    100x margin for the required examples.
  * DIVERGENCE_BUDGET = 2,000 beta-value steps: used for the two examples
    that must exhaust their budget (DEMO-09, DEMO-12). Any finite budget
    demonstrates exhaustion for a genuinely divergent program; this one is
    kept small purely so the demo finishes quickly.
  * OBS_BUDGET = 2,000 beta-value steps: the budget used for the separate
    observation-stage reduction (applying a value to STEP/BASE or to the
    boolean markers, or to a pair projection). Every required example
    decodes in well under 100 observation steps.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compiler import compile_expr
from evaluator import eval_source, eval_target, SInt, SBool
from decoders import observe_value, NAT, BOOL
from target_ast import print_term
from examples import DEMOS

EXEC_BUDGET = 200_000
DIVERGENCE_BUDGET = 2_000
OBS_BUDGET = 2_000

_KIND_MAP = {"nat": NAT, "bool": BOOL}

_SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_terms")


def _expected_source_side(dexp, expected_kind: str):
    """Obtain the source-side expected result by running the single shared
    evaluator's source path (unbounded, per the assignment) -- but only for
    examples the table marks as terminating; a divergent example's expected
    answer is "budget exhaustion", not a source-side value."""
    value = eval_source(dexp)
    if expected_kind == "nat":
        assert isinstance(value, SInt)
        return value.n
    assert isinstance(value, SBool)
    return value.b


def run_demo(verbose: bool = True):
    os.makedirs(_SAVE_DIR, exist_ok=True)
    rows = []
    all_ok = True
    for demo_id, description, dexp, kind, expected in DEMOS:
        compiled = compile_expr(dexp)
        printed = print_term(compiled)

        term_file = None
        if len(printed) > 300:
            term_file = os.path.join(_SAVE_DIR, f"{demo_id}.txt")
            with open(term_file, "w") as fh:
                fh.write(printed + "\n")

        divergent = expected is None
        exec_budget = DIVERGENCE_BUDGET if divergent else EXEC_BUDGET
        exec_result = eval_target(compiled, exec_budget)

        if exec_result.status == "exhausted":
            obs_status, decoded, obs_steps = "n/a (execution exhausted)", None, 0
        else:
            obs = observe_value(
                compiled, _KIND_MAP[kind], exec_budget=exec_budget, obs_budget=OBS_BUDGET
            )
            # observe_value re-runs execution internally to get a self
            # contained, budget-documented observation; exec_result above is
            # kept to report the *execution* step count on its own, per
            # DEM-02 ("execution reduction outcome and beta-value step
            # count, observation outcome and its separate beta-value step
            # count").
            obs_status, decoded, obs_steps = obs.status, obs.value, obs.steps

        if divergent:
            ok = exec_result.status == "exhausted"
            expected_repr = "budget exhaustion"
        else:
            ok = exec_result.status == "completed" and decoded == expected
            expected_repr = repr(expected)
        all_ok = all_ok and ok

        rows.append(
            dict(
                id=demo_id,
                description=description,
                term_repr=(printed if term_file is None else f"(saved: {term_file})"),
                exec_status=exec_result.status,
                exec_steps=exec_result.steps,
                exec_budget=exec_budget,
                obs_status=obs_status,
                obs_steps=obs_steps,
                obs_budget=OBS_BUDGET,
                decoded=decoded,
                expected=expected_repr,
                ok=ok,
            )
        )

    if verbose:
        for row in rows:
            print(f"{row['id']}: {row['description']}")
            print(f"  generated term : {row['term_repr']}")
            print(
                f"  execution      : {row['exec_status']} "
                f"({row['exec_steps']} / {row['exec_budget']} steps)"
            )
            print(
                f"  observation    : {row['obs_status']} "
                f"({row['obs_steps']} / {row['obs_budget']} steps)"
            )
            print(f"  decoded answer : {row['decoded']!r}")
            print(f"  expected answer: {row['expected']}")
            print(f"  result         : {'PASS' if row['ok'] else 'FAIL'}")
            print()
        print("ALL DEMOS PASSED" if all_ok else "SOME DEMOS FAILED")
    return rows, all_ok


if __name__ == "__main__":
    _, ok = run_demo(verbose=True)
    sys.exit(0 if ok else 1)
