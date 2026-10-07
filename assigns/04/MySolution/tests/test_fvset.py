"""Free-variable analysis (lambda1.d0exp_fvset): every constructor and scope rule."""
import unittest

from lambda1 import (D0Eapp, D0Ebtf, D0Efix, D0Eif0, D0Eint, D0Elam, D0Elet,
                     D0Eop1, D0Eop2, D0Epair, D0Epfst, D0Epsnd, D0Evar,
                     d0exp_fvset)

x, y, f = D0Evar("x"), D0Evar("y"), D0Evar("f")


class FreeVariables(unittest.TestCase):
    def fv(self, e):
        r = d0exp_fvset(e)
        self.assertIsInstance(r, frozenset)
        return r

    def test_constants_have_none(self):
        self.assertEqual(self.fv(D0Eint(1)), frozenset())
        self.assertEqual(self.fv(D0Ebtf(True)), frozenset())

    def test_var(self):
        self.assertEqual(self.fv(x), frozenset({"x"}))

    def test_op1_pfst_psnd(self):
        self.assertEqual(self.fv(D0Eop1("+1", x)), {"x"})
        self.assertEqual(self.fv(D0Epfst(x)), {"x"})
        self.assertEqual(self.fv(D0Epsnd(x)), {"x"})

    def test_op2_app_pair_collect_both_sides(self):
        for ctor in (lambda a, b: D0Eop2("+", a, b), D0Eapp, D0Epair):
            self.assertEqual(self.fv(ctor(x, y)), {"x", "y"})

    def test_if0_all_three_branches(self):
        self.assertEqual(self.fv(D0Eif0(D0Evar("c"), x, y)), {"c", "x", "y"})
        self.assertEqual(self.fv(D0Eif0(D0Ebtf(True), D0Eint(1), y)), {"y"})  # else branch
        self.assertEqual(self.fv(D0Eif0(D0Ebtf(True), x, D0Eint(1))), {"x"})  # then branch

    def test_lam_binds_parameter(self):
        self.assertEqual(self.fv(D0Elam("x", x)), frozenset())
        self.assertEqual(self.fv(D0Elam("x", D0Eop2("+", x, y))), {"y"})

    def test_fix_binds_name_and_parameter(self):
        body = D0Eapp(f, D0Eop2("+", x, y))
        self.assertEqual(self.fv(D0Efix("f", "x", body)), {"y"})

    def test_let_initializer_is_outside_scope(self):
        # let x = x in x : initializer's x is free, body's x is bound
        self.assertEqual(self.fv(D0Elet("x", x, x)), {"x"})
        self.assertEqual(self.fv(D0Elet("x", D0Eint(1), D0Eop2("+", x, y))), {"y"})

    def test_duplicates_collapse(self):
        self.assertEqual(self.fv(D0Eop2("+", x, D0Eop2("*", x, x))), {"x"})

    def test_nested_bindings_and_shadowing(self):
        e = D0Elam("x", D0Elam("y", D0Eop2("+", D0Eop2("+", x, y), D0Evar("z"))))
        self.assertEqual(self.fv(e), {"z"})
        # inner binding does not leak outwards
        e2 = D0Eop2("+", D0Elam("x", x), x)
        self.assertEqual(self.fv(e2), {"x"})
        # shadowing: inner let rebinds x, outer use after is still bound
        e3 = D0Elam("x", D0Elet("x", D0Eint(1), x))
        self.assertEqual(self.fv(e3), frozenset())

    def test_unused_binding_is_not_free(self):
        self.assertEqual(self.fv(D0Elam("unused", D0Eint(1))), frozenset())


if __name__ == "__main__":
    unittest.main()
