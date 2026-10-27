import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import church as C
from target_ast import Var, Lam, App, alpha_equivalent
from decoders import observe_nat, observe_bool, observe_value, NAT, BOOL, PAIR_KIND


class TestObserveNat(unittest.TestCase):
    def test_small_values(self):
        for n in range(8):
            r = observe_nat(C.NUM(n), 5000)
            self.assertEqual((r.status, r.value), ("ok", n))

    def test_accepts_alpha_renamed_encoding(self):
        # Build NUM(3) with differently-named binders by hand.
        renamed = Lam("succ", Lam("zero", App(Var("succ"), App(Var("succ"), App(Var("succ"), Var("zero"))))))
        self.assertTrue(alpha_equivalent(renamed, C.NUM(3)))
        r = observe_nat(renamed, 5000)
        self.assertEqual((r.status, r.value), ("ok", 3))

    def test_computed_encoding_still_decodes(self):
        # OBS-01: "computed encodings with redexes inside lambda bodies"
        # must still decode correctly. observe_nat's own probe reduces
        # its argument position along with everything else, so handing it
        # an unevaluated-but-closed arithmetic expression (rather than a
        # literal NUM(n)) must still decode to the right answer.
        add_term = App(App(C.ADD(), C.NUM(2)), C.NUM(3))
        r = observe_nat(add_term, 5000)
        self.assertEqual((r.status, r.value), ("ok", 5))

    def test_malformed_output_detected(self):
        # TRUE's shape (a 3-deep-nested lambda once applied to STEP) does
        # not match the expected 2-level numeral spine.
        r = observe_nat(C.TRUE(), 5000)
        self.assertEqual(r.status, "malformed")

    def test_budget_exhaustion_distinguished_from_malformed(self):
        omega_half = Lam("x", App(Var("x"), Var("x")))
        omega = App(omega_half, omega_half)
        r = observe_nat(omega, 10)
        self.assertEqual(r.status, "exhausted")
        self.assertIsNone(r.value)


class TestObserveBool(unittest.TestCase):
    def test_true_false(self):
        self.assertEqual(observe_bool(C.TRUE(), 1000).value, True)
        self.assertEqual(observe_bool(C.FALSE(), 1000).value, False)

    def test_church_zero_as_boolean(self):
        # ACC-11: Church zero decodes as False under the boolean kind
        # (it is alpha-equivalent to FALSE).
        r = observe_bool(C.NUM(0), 1000)
        self.assertEqual((r.status, r.value), ("ok", False))

    def test_church_zero_as_natural(self):
        r = observe_nat(C.NUM(0), 1000)
        self.assertEqual((r.status, r.value), ("ok", 0))

    def test_malformed_nonboolean(self):
        r = observe_bool(C.NUM(2), 1000)
        self.assertEqual(r.status, "malformed")

    def test_alpha_renamed_boolean(self):
        renamed_true = Lam("yes", Lam("no", Var("yes")))
        r = observe_bool(renamed_true, 1000)
        self.assertEqual((r.status, r.value), ("ok", True))


class TestObserveValuePipeline(unittest.TestCase):
    """OBS-02/OBS-03: evaluate to a value first (execution budget), then
    decode (observation budget); pairs recurse with expected component
    kinds."""

    def test_plain_nat_and_bool(self):
        self.assertEqual(
            observe_value(C.NUM(4), NAT, exec_budget=1000, obs_budget=1000).value, 4
        )
        self.assertEqual(
            observe_value(C.TRUE(), BOOL, exec_budget=1000, obs_budget=1000).value,
            True,
        )

    def test_unevaluated_program_is_executed_first(self):
        # ADD(2,3) is not yet a value; observe_value must reduce it.
        program = App(App(C.ADD(), C.NUM(2)), C.NUM(3))
        r = observe_value(program, NAT, exec_budget=5000, obs_budget=5000)
        self.assertEqual((r.status, r.value), ("ok", 5))

    def test_pair(self):
        pair = App(App(C.PAIR(), C.NUM(2)), C.TRUE())
        r = observe_value(pair, PAIR_KIND(NAT, BOOL), exec_budget=5000, obs_budget=5000)
        self.assertEqual((r.status, r.value), ("ok", (2, True)))

    def test_nested_pair_acc12(self):
        # ACC-12: pair (pair 2 true) 3
        inner = App(App(C.PAIR(), C.NUM(2)), C.TRUE())
        outer = App(App(C.PAIR(), inner), C.NUM(3))
        r = observe_value(
            outer, PAIR_KIND(PAIR_KIND(NAT, BOOL), NAT), exec_budget=20000, obs_budget=20000
        )
        self.assertEqual((r.status, r.value), ("ok", ((2, True), 3)))

    def test_execution_exhaustion_reported(self):
        omega_half = Lam("x", App(Var("x"), Var("x")))
        omega = App(omega_half, omega_half)
        r = observe_value(omega, NAT, exec_budget=5, obs_budget=1000)
        self.assertEqual(r.status, "exhausted")

    def test_pair_component_exhaustion_propagates(self):
        omega_half = Lam("x", App(Var("x"), Var("x")))
        omega = App(omega_half, omega_half)
        pair = App(App(C.PAIR(), omega), C.TRUE())
        r = observe_value(pair, PAIR_KIND(NAT, BOOL), exec_budget=20000, obs_budget=5)
        self.assertEqual(r.status, "exhausted")


if __name__ == "__main__":
    unittest.main()
