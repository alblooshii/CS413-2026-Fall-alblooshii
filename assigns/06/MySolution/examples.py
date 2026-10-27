"""Shared example source programs, built directly as D0E... AST nodes (no
parser is required or provided, per the assignment). Used by both demo.py
and the test suite so the two stay in sync.

`LOOP` denotes `(fix loop(x). loop x) 0`, which never terminates.
"""
from __future__ import annotations

import os
import sys

_ASSIGN05_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "05")
if _ASSIGN05_DIR not in sys.path:
    sys.path.insert(0, _ASSIGN05_DIR)

import lambda1_vp as S

LOOP = S.D0Eapp(
    S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
    S.D0Eint(0),
)

FACT = S.D0Efix(
    "fact",
    "n",
    S.D0Eif0(
        S.D0Eop2("==", S.D0Evar("n"), S.D0Eint(0)),
        S.D0Eint(1),
        S.D0Eop2(
            "*",
            S.D0Evar("n"),
            S.D0Eapp(S.D0Evar("fact"), S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(1))),
        ),
    ),
)

FIB = S.D0Efix(
    "fib",
    "n",
    S.D0Eif0(
        S.D0Eop2("<=", S.D0Evar("n"), S.D0Eint(1)),
        S.D0Evar("n"),
        S.D0Eop2(
            "+",
            S.D0Eapp(S.D0Evar("fib"), S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(1))),
            S.D0Eapp(S.D0Evar("fib"), S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(2))),
        ),
    ),
)

# The 14 mandatory end-to-end demonstrations (Assign06 Task 4 table /
# REQUIREMENTS.md Section 7.1, DEMO-01..DEMO-14). Each entry is
# (id, description, source AST, expected kind, expected value or None for
# budget exhaustion).
DEMOS = [
    (
        "DEMO-01",
        "2 + 3 * 4",
        S.D0Eop2("+", S.D0Eint(2), S.D0Eop2("*", S.D0Eint(3), S.D0Eint(4))),
        "nat",
        14,
    ),
    (
        "DEMO-02",
        "2 - 5",
        S.D0Eop2("-", S.D0Eint(2), S.D0Eint(5)),
        "nat",
        0,
    ),
    (
        "DEMO-03",
        "if 2 <= 3 then 7 else 9",
        S.D0Eif0(S.D0Eop2("<=", S.D0Eint(2), S.D0Eint(3)), S.D0Eint(7), S.D0Eint(9)),
        "nat",
        7,
    ),
    (
        "DEMO-04",
        "let x = 3 in (lam y. x + y) 4",
        S.D0Elet(
            "x",
            S.D0Eint(3),
            S.D0Eapp(
                S.D0Elam("y", S.D0Eop2("+", S.D0Evar("x"), S.D0Evar("y"))),
                S.D0Eint(4),
            ),
        ),
        "nat",
        7,
    ),
    (
        "DEMO-05",
        "fst (pair 2 true)",
        S.D0Epfst(S.D0Epair(S.D0Eint(2), S.D0Ebtf(True))),
        "nat",
        2,
    ),
    (
        "DEMO-06",
        "snd (pair 2 true)",
        S.D0Epsnd(S.D0Epair(S.D0Eint(2), S.D0Ebtf(True))),
        "bool",
        True,
    ),
    (
        "DEMO-07",
        "(lam f. f 3) (lam x. x + 1)",
        S.D0Eapp(
            S.D0Elam("f", S.D0Eapp(S.D0Evar("f"), S.D0Eint(3))),
            S.D0Elam("x", S.D0Eop2("+", S.D0Evar("x"), S.D0Eint(1))),
        ),
        "nat",
        4,
    ),
    (
        "DEMO-08",
        "if true then 1 else LOOP",
        S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), LOOP),
        "nat",
        1,
    ),
    (
        "DEMO-09",
        "(lam x. 0) LOOP",
        S.D0Eapp(S.D0Elam("x", S.D0Eint(0)), LOOP),
        "nat",
        None,  # budget exhaustion
    ),
    (
        "DEMO-10",
        "recursive factorial applied to 4",
        S.D0Eapp(FACT, S.D0Eint(4)),
        "nat",
        24,
    ),
    (
        "DEMO-11",
        "recursive Fibonacci applied to 5",
        S.D0Eapp(FIB, S.D0Eint(5)),
        "nat",
        5,
    ),
    (
        "DEMO-12",
        "LOOP",
        LOOP,
        "nat",
        None,  # budget exhaustion
    ),
    (
        "DEMO-13",
        "true and false",
        S.D0Eop2("and", S.D0Ebtf(True), S.D0Ebtf(False)),
        "bool",
        False,
    ),
    (
        "DEMO-14",
        "false or true",
        S.D0Eop2("or", S.D0Ebtf(False), S.D0Ebtf(True)),
        "bool",
        True,
    ),
]
