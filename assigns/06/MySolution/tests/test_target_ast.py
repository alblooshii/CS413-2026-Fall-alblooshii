import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from target_ast import Var, Lam, App, free_vars, substitute, print_term, alpha_equivalent


class TestPrinter(unittest.TestCase):
    """TGT-02 / ACC-13: exact recursive print formats."""

    def test_var(self):
        self.assertEqual(print_term(Var("x")), "x")

    def test_lam(self):
        self.assertEqual(print_term(Lam("x", Var("x"))), "(lam x. x)")

    def test_app(self):
        self.assertEqual(print_term(App(Var("f"), Var("x"))), "(f x)")

    def test_nested(self):
        t = App(Lam("x", App(Var("x"), Var("x"))), Lam("y", Var("y")))
        self.assertEqual(print_term(t), "((lam x. (x x)) (lam y. y))")


class TestFreeVars(unittest.TestCase):
    def test_var(self):
        self.assertEqual(free_vars(Var("x")), frozenset({"x"}))

    def test_lam_binds(self):
        self.assertEqual(free_vars(Lam("x", Var("x"))), frozenset())
        self.assertEqual(free_vars(Lam("x", Var("y"))), frozenset({"y"}))

    def test_app_union(self):
        self.assertEqual(
            free_vars(App(Var("x"), Var("y"))), frozenset({"x", "y"})
        )

    def test_nested_shadowing(self):
        # lam x. lam x. x  -- inner x shadows; no free vars
        t = Lam("x", Lam("x", Var("x")))
        self.assertEqual(free_vars(t), frozenset())


class TestSubstitution(unittest.TestCase):
    """Testing obligation #1: substitution with shadowing and capture
    hazards, independent of closed-term execution."""

    def test_simple_replacement(self):
        t = Lam("w", Var("x"))
        r = substitute(t, "x", Var("q"))
        self.assertEqual(print_term(r), "(lam w. q)")

    def test_no_op_on_unrelated_name(self):
        t = Var("y")
        r = substitute(t, "x", Var("q"))
        self.assertIs(r, t)

    def test_shadowing_is_a_no_op_inside(self):
        # substituting x in (lam x. x) must not touch the bound x
        t = Lam("x", Var("x"))
        r = substitute(t, "x", Var("q"))
        self.assertEqual(print_term(r), "(lam x. x)")
        self.assertIs(r, t)

    def test_capture_avoidance_acc01(self):
        # ACC-01: substitute x := y directly in `lam y. x`.
        # Must produce an alpha-equivalent of `lam fresh. y`, with `y`
        # remaining free (not captured by the renamed binder).
        term = Lam("y", Var("x"))
        result = substitute(term, "x", Var("y"))
        self.assertTrue(alpha_equivalent(result, Lam("anything", Var("y"))))
        self.assertIn("y", free_vars(result))
        self.assertNotEqual(result.name, "y")  # the binder itself was renamed

    def test_capture_avoidance_nested(self):
        # lam a. lam b. a, substitute a := (b c)  -- "a" is bound by the
        # OUTER lambda, so only the free occurrence inside should move,
        # and nothing here should actually trigger renaming since we are
        # substituting into the body under the *outer* binder "a" itself,
        # which shadows -- this checks the inner "b" binder is untouched.
        t = Lam("b", Var("a"))
        repl = App(Var("b"), Var("c"))
        r = substitute(t, "a", repl)
        # b must have been renamed since repl contains a free "b"
        self.assertNotEqual(r.name, "b")
        self.assertTrue(alpha_equivalent(r, Lam("fresh", App(Var("b"), Var("c")))))

    def test_does_not_mutate_input(self):
        t = Lam("y", Var("x"))
        t_copy_repr = print_term(t)
        substitute(t, "x", Var("y"))
        self.assertEqual(print_term(t), t_copy_repr)

    def test_free_variable_preserved_when_no_hazard(self):
        t = App(Var("x"), Var("z"))
        r = substitute(t, "x", Var("q"))
        self.assertEqual(free_vars(r), frozenset({"q", "z"}))

    def test_double_substitution_distinct_fresh_names(self):
        # lam y. lam y_1. x  -- substituting x with something containing
        # both y and y_1 free must avoid colliding with either binder.
        t = Lam("y", Lam("y_1", Var("x")))
        repl = App(Var("y"), Var("y_1"))
        r = substitute(t, "x", repl)
        self.assertNotIn(r.name, {"y", "y_1"})
        inner = r.body
        self.assertNotIn(inner.name, {"y", "y_1", r.name})


class TestAlphaEquivalence(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(alpha_equivalent(Var("x"), Var("x")))

    def test_renamed_bound_var(self):
        self.assertTrue(
            alpha_equivalent(Lam("x", Var("x")), Lam("y", Var("y")))
        )

    def test_distinct_free_vars_not_equivalent(self):
        self.assertFalse(alpha_equivalent(Var("x"), Var("y")))

    def test_distinct_structure_not_equivalent(self):
        self.assertFalse(
            alpha_equivalent(Lam("x", Var("x")), Lam("x", App(Var("x"), Var("x"))))
        )


if __name__ == "__main__":
    unittest.main()
