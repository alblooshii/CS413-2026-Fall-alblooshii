import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import church as C
from target_ast import free_vars, App
from evaluator import eval_target
from decoders import observe_nat, observe_bool

BUDGET = 20_000


def dec_nat(term, budget=BUDGET):
    r = observe_nat(term, budget)
    assert r.status == "ok", r
    return r.value


def dec_bool(term, budget=BUDGET):
    r = observe_bool(term, budget)
    assert r.status == "ok", r
    return r.value


class TestEveryCombinatorIsClosed(unittest.TestCase):
    """ENC-01: every library combinator shall be closed."""

    def test_all_closed(self):
        builders = [
            C.I, C.TRUE, C.FALSE, C.PAIR, C.FST, C.SND, C.Z, C.SUCC, C.PRED,
            C.ADD, C.SUB, C.MUL, C.ISZERO, C.NOT, C.AND, C.OR,
            C.LEQ, C.LT, C.GT, C.GEQ, C.EQ, C.NEQ,
        ]
        for b in builders:
            with self.subTest(builder=b.__name__):
                self.assertEqual(free_vars(b()), frozenset())

    def test_numerals_closed(self):
        for n in range(6):
            self.assertEqual(free_vars(C.NUM(n)), frozenset())

    def test_negative_numeral_rejected(self):
        with self.assertRaises(ValueError):
            C.NUM(-1)


class TestNumerals(unittest.TestCase):
    def test_small_numerals_decode(self):
        for n in range(8):
            self.assertEqual(dec_nat(C.NUM(n)), n)


class TestPredecessor(unittest.TestCase):
    """ENC-02: predecessor of zero is zero; general case correct."""

    def test_pred_of_zero_is_zero(self):
        self.assertEqual(dec_nat(App(C.PRED(), C.NUM(0))), 0)

    def test_pred_general(self):
        for n in range(1, 8):
            self.assertEqual(dec_nat(App(C.PRED(), C.NUM(n))), n - 1)


class TestArithmetic(unittest.TestCase):
    def test_add(self):
        for m in range(5):
            for n in range(5):
                term = App(App(C.ADD(), C.NUM(m)), C.NUM(n))
                self.assertEqual(dec_nat(term), m + n, (m, n))

    def test_truncated_sub(self):
        for m in range(6):
            for n in range(6):
                term = App(App(C.SUB(), C.NUM(m)), C.NUM(n))
                self.assertEqual(dec_nat(term), max(m - n, 0), (m, n))

    def test_mul(self):
        for m in range(5):
            for n in range(5):
                term = App(App(C.MUL(), C.NUM(m)), C.NUM(n))
                self.assertEqual(dec_nat(term), m * n, (m, n))


class TestComparisons(unittest.TestCase):
    """ACC-05: every encoding tested independently, including equal and
    unequal operands and both outcomes of every comparison."""

    def test_all_comparisons(self):
        ops = {
            "<": (C.LT, lambda m, n: m < n),
            "<=": (C.LEQ, lambda m, n: m <= n),
            ">": (C.GT, lambda m, n: m > n),
            ">=": (C.GEQ, lambda m, n: m >= n),
            "==": (C.EQ, lambda m, n: m == n),
            "!=": (C.NEQ, lambda m, n: m != n),
        }
        for name, (builder, ref) in ops.items():
            saw_true = saw_false = False
            for m in range(5):
                for n in range(5):
                    term = App(App(builder(), C.NUM(m)), C.NUM(n))
                    got = dec_bool(term)
                    expected = ref(m, n)
                    self.assertEqual(got, expected, (name, m, n))
                    saw_true = saw_true or got
                    saw_false = saw_false or not got
            self.assertTrue(saw_true, f"{name}: never saw True")
            self.assertTrue(saw_false, f"{name}: never saw False")

    def test_equal_and_unequal_operands_explicit(self):
        self.assertTrue(dec_bool(App(App(C.EQ(), C.NUM(3)), C.NUM(3))))
        self.assertFalse(dec_bool(App(App(C.EQ(), C.NUM(3)), C.NUM(4))))
        self.assertFalse(dec_bool(App(App(C.NEQ(), C.NUM(3)), C.NUM(3))))
        self.assertTrue(dec_bool(App(App(C.NEQ(), C.NUM(3)), C.NUM(4))))


class TestBooleans(unittest.TestCase):
    """ACC-05: complete boolean truth tables."""

    def test_true_false_decode(self):
        self.assertTrue(dec_bool(C.TRUE()))
        self.assertFalse(dec_bool(C.FALSE()))

    def test_not(self):
        self.assertFalse(dec_bool(App(C.NOT(), C.TRUE())))
        self.assertTrue(dec_bool(App(C.NOT(), C.FALSE())))

    def test_and_or_truth_tables(self):
        for p in (True, False):
            for q in (True, False):
                pt = C.TRUE() if p else C.FALSE()
                qt = C.TRUE() if q else C.FALSE()
                self.assertEqual(
                    dec_bool(App(App(C.AND(), pt), qt)), p and q, (p, q)
                )
                self.assertEqual(
                    dec_bool(App(App(C.OR(), pt), qt)), p or q, (p, q)
                )


class TestPairs(unittest.TestCase):
    def test_fst_snd(self):
        pair = App(App(C.PAIR(), C.NUM(2)), C.TRUE())
        self.assertEqual(dec_nat(App(C.FST(), pair)), 2)
        self.assertTrue(dec_bool(App(C.SND(), pair)))


class TestIdentityAndZ(unittest.TestCase):
    def test_identity(self):
        r = eval_target(App(C.I(), C.NUM(3)), 1000)
        self.assertEqual(r.status, "completed")
        self.assertEqual(dec_nat(r.term), 3)

    def test_z_drives_recursion(self):
        # fact-like recursive function built directly with Z, independent
        # of the compiler, as an additional encoding-level sanity check.
        # Built WITHOUT the compiler's delayed-branch helper: since
        # ISZERO n yields a Church boolean, we must still force only the
        # selected branch, so apply the boolean to two thunks and force
        # with I, exactly as the compiler does for `if`.
        from target_ast import Var, Lam, App as A

        selected = A(
            A(A(C.ISZERO(), Var("n")), Lam("_u", C.NUM(1))),
            Lam(
                "_v",
                A(A(C.MUL(), Var("n")), A(Var("fact"), A(C.PRED(), Var("n")))),
            ),
        )
        forced = A(selected, C.I())
        direct_fact = Lam("fact", Lam("n", forced))
        term = A(A(C.Z(), direct_fact), C.NUM(4))
        self.assertEqual(dec_nat(term, budget=50_000), 24)


if __name__ == "__main__":
    unittest.main()
