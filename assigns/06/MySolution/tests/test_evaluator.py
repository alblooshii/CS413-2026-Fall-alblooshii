import copy
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "05"))

from target_ast import Var, Lam, App, print_term
from evaluator import eval_target, eval_source, EvalError, SInt, SBool, SPair
import lambda1_vp as S

I = Lam("x", Var("x"))


class TestTargetReductionOrder(unittest.TestCase):
    """Testing obligation #2: left-to-right CBV traversal, no reduction
    under lambdas, zero-step values, determinism, budget exhaustion."""

    def test_lambda_is_value_in_zero_steps_even_with_internal_redexes(self):
        # ACC-02
        t = Lam("x", App(Lam("y", Var("y")), Var("x")))
        r = eval_target(t, 1000)
        self.assertEqual(r.status, "completed")
        self.assertEqual(r.steps, 0)
        self.assertIs(r.term, t)  # unreduced: no reduction under the binder

    def test_left_to_right_order_and_outer_contraction_last(self):
        # ACC-02: (I I) (I I) evaluates its left child, then right, then
        # contracts the outer application: 3 steps total.
        t = App(App(I, I), App(I, I))
        r = eval_target(t, 1000)
        self.assertEqual(r.status, "completed")
        self.assertEqual(r.steps, 3)
        self.assertEqual(print_term(r.term), "(lam x. x)")

    def test_budget_boundaries(self):
        # ACC-03
        r_i0 = eval_target(I, 0)
        self.assertEqual((r_i0.status, r_i0.steps), ("completed", 0))

        r_ii0 = eval_target(App(I, I), 0)
        self.assertEqual((r_ii0.status, r_ii0.steps), ("exhausted", 0))

        r_ii1 = eval_target(App(I, I), 1)
        self.assertEqual((r_ii1.status, r_ii1.steps), ("completed", 1))

    def test_deterministic_and_input_preserved(self):
        # ACC-04
        t = App(App(I, I), App(I, I))
        snapshot = copy.deepcopy(t)
        r1 = eval_target(t, 1000)
        r2 = eval_target(t, 1000)
        self.assertEqual(t, snapshot)
        self.assertEqual((r1.status, r1.steps), (r2.status, r2.steps))
        self.assertEqual(print_term(r1.term), print_term(r2.term))

    def test_exhaustion_on_diverging_term(self):
        omega_half = Lam("x", App(Var("x"), Var("x")))
        omega = App(omega_half, omega_half)
        r = eval_target(omega, 50)
        self.assertEqual(r.status, "exhausted")
        self.assertEqual(r.steps, 50)

    def test_rejects_open_terms(self):
        with self.assertRaises(EvalError):
            eval_target(Var("free"), 10)
        with self.assertRaises(EvalError):
            eval_target(Lam("x", Var("y")), 10)

    def test_negative_budget_rejected(self):
        with self.assertRaises(ValueError):
            eval_target(I, -1)


class TestSourceEvaluation(unittest.TestCase):
    """Source-side evaluation: left-to-right CBV, and/or short-circuit,
    if0 selects only one branch, lexical scope and shadowing, fix binders
    including the coincident case."""

    def test_arithmetic(self):
        e = S.D0Eop2("+", S.D0Eint(2), S.D0Eop2("*", S.D0Eint(3), S.D0Eint(4)))
        self.assertEqual(eval_source(e), SInt(14))

    def test_truncated_subtraction(self):
        e = S.D0Eop2("-", S.D0Eint(2), S.D0Eint(5))
        self.assertEqual(eval_source(e), SInt(0))

    def test_not(self):
        self.assertEqual(eval_source(S.D0Eop1("not", S.D0Ebtf(True))), SBool(False))
        self.assertEqual(eval_source(S.D0Eop1("not", S.D0Ebtf(False))), SBool(True))

    def test_and_short_circuits(self):
        loop = S.D0Eapp(
            S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
            S.D0Eint(0),
        )
        e = S.D0Eop2("and", S.D0Ebtf(False), loop)
        self.assertEqual(eval_source(e), SBool(False))

    def test_or_short_circuits(self):
        loop = S.D0Eapp(
            S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
            S.D0Eint(0),
        )
        e = S.D0Eop2("or", S.D0Ebtf(True), loop)
        self.assertEqual(eval_source(e), SBool(True))

    def test_if0_selects_one_branch_only(self):
        loop = S.D0Eapp(
            S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
            S.D0Eint(0),
        )
        e = S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), loop)
        self.assertEqual(eval_source(e), SInt(1))

    def test_let_scope(self):
        # let x = x in x  evaluated with x free in the environment: the
        # initializer refers to the OUTER x, not the let-bound one.
        from evaluator import EnvCons, EnvNil

        env = EnvCons("x", SInt(99), EnvNil())
        e = S.D0Elet("x", S.D0Evar("x"), S.D0Evar("x"))
        self.assertEqual(eval_source(e, env), SInt(99))

    def test_nested_shadowing(self):
        e = S.D0Elam(
            "x", S.D0Elam("x", S.D0Eop2("+", S.D0Evar("x"), S.D0Eint(1)))
        )
        # apply outer x=10, inner x=5 -> inner shadows -> result 6
        applied = S.D0Eapp(S.D0Eapp(e, S.D0Eint(10)), S.D0Eint(5))
        self.assertEqual(eval_source(applied), SInt(6))

    def test_pairs(self):
        e = S.D0Epair(S.D0Eint(2), S.D0Ebtf(True))
        self.assertEqual(eval_source(e), SPair(SInt(2), SBool(True)))
        self.assertEqual(eval_source(S.D0Epfst(e)), SInt(2))
        self.assertEqual(eval_source(S.D0Epsnd(e)), SBool(True))

    def test_nested_pairs(self):
        e = S.D0Epair(S.D0Epair(S.D0Eint(2), S.D0Ebtf(True)), S.D0Eint(3))
        v = eval_source(e)
        self.assertEqual(v, SPair(SPair(SInt(2), SBool(True)), SInt(3)))

    def test_fix_recursion_factorial(self):
        fact = S.D0Efix(
            "fact",
            "n",
            S.D0Eif0(
                S.D0Eop2("==", S.D0Evar("n"), S.D0Eint(0)),
                S.D0Eint(1),
                S.D0Eop2(
                    "*",
                    S.D0Evar("n"),
                    S.D0Eapp(
                        S.D0Evar("fact"),
                        S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(1)),
                    ),
                ),
            ),
        )
        self.assertEqual(eval_source(S.D0Eapp(fact, S.D0Eint(4))), SInt(24))

    def test_fix_coincident_binder(self):
        # ACC-07: (fix f(f). f) 3 -- parameter shadows function name
        e = S.D0Eapp(S.D0Efix("f", "f", S.D0Evar("f")), S.D0Eint(3))
        self.assertEqual(eval_source(e), SInt(3))

    def test_all_comparisons_and_both_outcomes(self):
        cases = [
            ("<", 2, 3, True), ("<", 3, 2, False),
            ("<=", 2, 2, True), ("<=", 3, 2, False),
            (">", 3, 2, True), (">", 2, 3, False),
            (">=", 2, 2, True), (">=", 2, 3, False),
            ("==", 2, 2, True), ("==", 2, 3, False),
            ("!=", 2, 3, True), ("!=", 2, 2, False),
        ]
        for op, m, n, expected in cases:
            e = S.D0Eop2(op, S.D0Eint(m), S.D0Eint(n))
            self.assertEqual(eval_source(e), SBool(expected), (op, m, n))

    def test_both_booleans_and_truth_table(self):
        for p in (True, False):
            for q in (True, False):
                self.assertEqual(
                    eval_source(S.D0Eop2("and", S.D0Ebtf(p), S.D0Ebtf(q))),
                    SBool(p and q),
                )
                self.assertEqual(
                    eval_source(S.D0Eop2("or", S.D0Ebtf(p), S.D0Ebtf(q))),
                    SBool(p or q),
                )

    def test_unbound_variable_errors(self):
        with self.assertRaises(EvalError):
            eval_source(S.D0Evar("nope"))

    def test_unsupported_op_rejected_at_eval_time(self):
        with self.assertRaises(EvalError):
            eval_source(S.D0Eop2("/", S.D0Eint(4), S.D0Eint(2)))


if __name__ == "__main__":
    unittest.main()
