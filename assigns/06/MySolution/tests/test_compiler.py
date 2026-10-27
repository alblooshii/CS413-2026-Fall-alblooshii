import os
import sys
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "05"))

import lambda1_vp as S
from compiler import compile_expr, CompileError
from evaluator import eval_target
from decoders import observe_nat, observe_bool
from target_ast import Var, Lam, App, free_vars, Term

BUDGET = 200_000
OBS_BUDGET = 2_000


def run_nat(dexp):
    r = observe_nat(
        eval_target(compile_expr(dexp), BUDGET).term, OBS_BUDGET
    )
    return r


def run_bool(dexp):
    r = observe_bool(
        eval_target(compile_expr(dexp), BUDGET).term, OBS_BUDGET
    )
    return r


def nat_of(dexp):
    exec_r = eval_target(compile_expr(dexp), BUDGET)
    assert exec_r.status == "completed", exec_r.status
    r = observe_nat(exec_r.term, OBS_BUDGET)
    assert r.status == "ok", r
    return r.value


def bool_of(dexp):
    exec_r = eval_target(compile_expr(dexp), BUDGET)
    assert exec_r.status == "completed", exec_r.status
    r = observe_bool(exec_r.term, OBS_BUDGET)
    assert r.status == "ok", r
    return r.value


class TestEverySourceConstruct(unittest.TestCase):
    """Testing obligation #3: every required source constructor and
    operator, including zero, predecessor of zero, equal/unequal
    operands, both comparison outcomes, both booleans, all boolean
    truth-table cases."""

    def test_int_and_zero(self):
        self.assertEqual(nat_of(S.D0Eint(0)), 0)
        self.assertEqual(nat_of(S.D0Eint(7)), 7)

    def test_btf(self):
        self.assertTrue(bool_of(S.D0Ebtf(True)))
        self.assertFalse(bool_of(S.D0Ebtf(False)))

    def test_var_and_lam_and_app(self):
        e = S.D0Eapp(S.D0Elam("x", S.D0Eop2("+", S.D0Evar("x"), S.D0Eint(1))), S.D0Eint(4))
        self.assertEqual(nat_of(e), 5)

    def test_not(self):
        self.assertFalse(bool_of(S.D0Eop1("not", S.D0Ebtf(True))))
        self.assertTrue(bool_of(S.D0Eop1("not", S.D0Ebtf(False))))

    def test_all_binops_both_outcomes(self):
        for op, m, n, expect_nat in [("+", 2, 3, 5), ("-", 2, 5, 0), ("-", 5, 2, 3), ("*", 3, 4, 12)]:
            self.assertEqual(nat_of(S.D0Eop2(op, S.D0Eint(m), S.D0Eint(n))), expect_nat, (op, m, n))
        for op, m, n, expect_bool in [
            ("<", 2, 3, True), ("<", 3, 2, False),
            ("<=", 2, 2, True), ("<=", 3, 2, False),
            (">", 3, 2, True), (">", 2, 3, False),
            (">=", 2, 2, True), (">=", 2, 3, False),
            ("==", 4, 4, True), ("==", 4, 5, False),
            ("!=", 4, 5, True), ("!=", 4, 4, False),
        ]:
            self.assertEqual(bool_of(S.D0Eop2(op, S.D0Eint(m), S.D0Eint(n))), expect_bool, (op, m, n))

    def test_if0(self):
        self.assertEqual(nat_of(S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), S.D0Eint(2))), 1)
        self.assertEqual(nat_of(S.D0Eif0(S.D0Ebtf(False), S.D0Eint(1), S.D0Eint(2))), 2)

    def test_let(self):
        e = S.D0Elet("x", S.D0Eint(3), S.D0Eop2("+", S.D0Evar("x"), S.D0Eint(4)))
        self.assertEqual(nat_of(e), 7)

    def test_pair_fst_snd(self):
        e = S.D0Epair(S.D0Eint(2), S.D0Ebtf(True))
        self.assertEqual(nat_of(S.D0Epfst(e)), 2)
        self.assertTrue(bool_of(S.D0Epsnd(e)))

    def test_fix(self):
        fact = S.D0Efix(
            "fact", "n",
            S.D0Eif0(
                S.D0Eop2("==", S.D0Evar("n"), S.D0Eint(0)),
                S.D0Eint(1),
                S.D0Eop2("*", S.D0Evar("n"),
                         S.D0Eapp(S.D0Evar("fact"), S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(1)))),
            ),
        )
        self.assertEqual(nat_of(S.D0Eapp(fact, S.D0Eint(5))), 120)

    def test_and_or_full_truth_table(self):
        for p in (True, False):
            for q in (True, False):
                self.assertEqual(
                    bool_of(S.D0Eop2("and", S.D0Ebtf(p), S.D0Ebtf(q))), p and q, (p, q)
                )
                self.assertEqual(
                    bool_of(S.D0Eop2("or", S.D0Ebtf(p), S.D0Ebtf(q))), p or q, (p, q)
                )


class TestScopeAndShadowing(unittest.TestCase):
    """Testing obligation #4: nested lets/lambdas, let-initializer scope,
    both fix binders incl. coincident, open expressions, names that
    collide with encoding names; free-variable preservation; input
    immutability. (ACC-06, ACC-07, CMP-04..CMP-06)"""

    def test_let_does_not_bind_in_initializer(self):
        # let x = x in x, with outer x free: initializer's x is the free one
        e = S.D0Elet("x", S.D0Evar("x"), S.D0Evar("x"))
        compiled = compile_expr(e)
        self.assertEqual(free_vars(compiled), frozenset({"x"}))

    def test_nested_lambdas_shadowing(self):
        e = S.D0Elam("x", S.D0Elam("x", S.D0Eop2("+", S.D0Evar("x"), S.D0Eint(1))))
        applied = S.D0Eapp(S.D0Eapp(e, S.D0Eint(100)), S.D0Eint(5))
        self.assertEqual(nat_of(applied), 6)

    def test_coincident_fix_binder(self):
        # ACC-07: (fix f(f). f) 3  ==> 3
        e = S.D0Eapp(S.D0Efix("f", "f", S.D0Evar("f")), S.D0Eint(3))
        self.assertEqual(nat_of(e), 3)

    def test_distinct_fix_binders_capture_hazard(self):
        # fix f(x). if x == 0 then f else x  -- "f" (the function name)
        # used as a *value* inside the body; must still resolve correctly
        # after compilation to Z, i.e. must not be captured/clobbered by
        # Z's own internal binder names.
        fx = S.D0Efix(
            "f", "x",
            S.D0Eif0(
                S.D0Eop2("==", S.D0Evar("x"), S.D0Eint(0)),
                S.D0Eint(42),
                S.D0Eapp(S.D0Evar("f"), S.D0Eop2("-", S.D0Evar("x"), S.D0Eint(1))),
            ),
        )
        self.assertEqual(nat_of(S.D0Eapp(fx, S.D0Eint(3))), 42)

    def test_open_expression_preserves_free_vars(self):
        e = S.D0Elam("y", S.D0Eop2("+", S.D0Evar("x"), S.D0Evar("y")))
        compiled = compile_expr(e)
        self.assertEqual(free_vars(compiled), S.d0exp_fvset(e))

    def test_names_colliding_with_encoding_names(self):
        # free s, z, t, f, x must all survive compilation untouched and
        # distinct, per CMP-06 ("do not reserve common source names").
        e = S.D0Epair(
            S.D0Epair(S.D0Evar("s"), S.D0Evar("z")),
            S.D0Epair(S.D0Evar("t"), S.D0Epair(S.D0Evar("f"), S.D0Evar("x"))),
        )
        compiled = compile_expr(e)
        self.assertEqual(free_vars(compiled), frozenset({"s", "z", "t", "f", "x"}))
        self.assertEqual(free_vars(compiled), S.d0exp_fvset(e))

    def test_compilation_does_not_mutate_source(self):
        e = S.D0Eop2("+", S.D0Eint(2), S.D0Eint(3))
        before_repr = repr(e)
        compile_expr(e)
        self.assertEqual(repr(e), before_repr)

    def test_repeated_calls_follow_documented_policy(self):
        # fresh_name's policy (names.py) is deterministic: compiling the
        # same if-expression twice must produce identical fresh names.
        e = S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), S.D0Eint(2))
        c1 = compile_expr(e)
        c2 = compile_expr(e)
        self.assertEqual(c1, c2)


class TestDivergenceHandling(unittest.TestCase):
    """Testing obligation #5: unselected divergence is skipped; diverging
    function arguments, let initializers, and pair components exhaust
    the budget even if unused. (ACC-08)"""

    @staticmethod
    def _loop():
        return S.D0Eapp(
            S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
            S.D0Eint(0),
        )

    def test_if_true_skips_diverging_else(self):
        e = S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), self._loop())
        self.assertEqual(nat_of(e), 1)

    def test_and_false_skips_diverging_right(self):
        e = S.D0Eop2("and", S.D0Ebtf(False), self._loop())
        # right side would need to be boolean-typed to decode as bool, so
        # just check it decodes as FALSE without hanging.
        self.assertFalse(bool_of(e))

    def test_or_true_skips_diverging_right(self):
        e = S.D0Eop2("or", S.D0Ebtf(True), self._loop())
        self.assertTrue(bool_of(e))

    def test_let_initializer_divergence_exhausts(self):
        e = S.D0Elet("x", self._loop(), S.D0Eint(2))
        r = eval_target(compile_expr(e), 2000)
        self.assertEqual(r.status, "exhausted")

    def test_pair_first_component_divergence_exhausts(self):
        e = S.D0Epfst(S.D0Epair(S.D0Eint(2), self._loop()))
        r = eval_target(compile_expr(e), 2000)
        self.assertEqual(r.status, "exhausted")

    def test_pair_second_component_divergence_exhausts(self):
        e = S.D0Epsnd(S.D0Epair(self._loop(), S.D0Ebtf(True)))
        r = eval_target(compile_expr(e), 2000)
        self.assertEqual(r.status, "exhausted")

    def test_function_argument_divergence_exhausts_even_if_unused(self):
        e = S.D0Eapp(S.D0Elam("x", S.D0Eint(0)), self._loop())
        r = eval_target(compile_expr(e), 2000)
        self.assertEqual(r.status, "exhausted")


class TestRejectionOfUnsupportedForms(unittest.TestCase):
    """Testing obligation #6 (rejection half) / CMP-07 / ACC-09: negative
    literals and unsupported operators rejected, including in unselected
    branches and unapplied function bodies."""

    def test_negative_literal_top_level(self):
        with self.assertRaises(CompileError):
            compile_expr(S.D0Eint(-1))

    def test_negative_literal_in_unselected_branch(self):
        bad = S.D0Eif0(S.D0Ebtf(True), S.D0Eint(1), S.D0Eint(-5))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_negative_literal_in_unapplied_lambda_body(self):
        bad = S.D0Elam("x", S.D0Eint(-3))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_division_rejected(self):
        bad = S.D0Eop2("/", S.D0Eint(4), S.D0Eint(2))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_division_rejected_in_unselected_branch(self):
        bad = S.D0Eif0(
            S.D0Ebtf(True), S.D0Eint(1), S.D0Eop2("/", S.D0Eint(4), S.D0Eint(2))
        )
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_unsupported_unary_operator_rejected(self):
        bad = S.D0Eop1("neg", S.D0Eint(3))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_unsupported_unary_operator_in_unapplied_body(self):
        bad = S.D0Elam("x", S.D0Eop1("neg", S.D0Eint(3)))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_unsupported_binary_operator_spelling(self):
        bad = S.D0Eop2("mod", S.D0Eint(4), S.D0Eint(2))
        with self.assertRaises(CompileError):
            compile_expr(bad)

    def test_error_message_identifies_offender(self):
        try:
            compile_expr(S.D0Eint(-5))
        except CompileError as e:
            self.assertIn("-5", str(e))
        try:
            compile_expr(S.D0Eop2("/", S.D0Eint(1), S.D0Eint(1)))
        except CompileError as e:
            self.assertIn("/", str(e))


class TestCompositionalityAndPurity(unittest.TestCase):
    """Testing obligation #7 / ACC-10: compiler output uses only the three
    target constructors; library combinators have no free variables;
    compilation does not call the shared evaluator."""

    def test_output_uses_only_three_forms(self):
        e = S.D0Eapp(
            S.D0Efix(
                "fact", "n",
                S.D0Eif0(
                    S.D0Eop2("==", S.D0Evar("n"), S.D0Eint(0)),
                    S.D0Eint(1),
                    S.D0Eop2("*", S.D0Evar("n"),
                             S.D0Eapp(S.D0Evar("fact"), S.D0Eop2("-", S.D0Evar("n"), S.D0Eint(1)))),
                ),
            ),
            S.D0Eint(3),
        )
        compiled = compile_expr(e)
        self._assert_only_three_forms(compiled)

    def _assert_only_three_forms(self, t):
        self.assertIsInstance(t, (Var, Lam, App))
        if isinstance(t, Lam):
            self._assert_only_three_forms(t.body)
        elif isinstance(t, App):
            self._assert_only_three_forms(t.fn)
            self._assert_only_three_forms(t.arg)

    def test_compiler_module_does_not_import_evaluator(self):
        import compiler as compiler_module
        self.assertNotIn("evaluator", dir(compiler_module))

    def test_compilation_never_calls_eval_target_or_eval_source(self):
        # Patch evaluator's entry points to blow up if invoked; compiling
        # arithmetic and a divergent program must still succeed.
        import evaluator

        def _boom(*args, **kwargs):
            raise AssertionError("compilation must not invoke the evaluator")

        orig_target, orig_source = evaluator.eval_target, evaluator.eval_source
        evaluator.eval_target = _boom
        evaluator.eval_source = _boom
        try:
            arithmetic = S.D0Eop2("+", S.D0Eint(2), S.D0Eint(3))
            compile_expr(arithmetic)  # must not raise AssertionError
            loop = S.D0Eapp(
                S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
                S.D0Eint(0),
            )
            compile_expr(loop)  # must compile without attempting to run it
        finally:
            evaluator.eval_target = orig_target
            evaluator.eval_source = orig_source

    def test_compilation_preserves_source_ast_snapshot(self):
        loop = S.D0Eapp(
            S.D0Efix("loop", "x", S.D0Eapp(S.D0Evar("loop"), S.D0Evar("x"))),
            S.D0Eint(0),
        )
        before = repr(loop)
        compile_expr(loop)
        self.assertEqual(repr(loop), before)


if __name__ == "__main__":
    unittest.main()
