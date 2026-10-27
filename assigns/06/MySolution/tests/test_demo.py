"""Testing obligation #6 (positive half): all 14 required demonstrations,
run end to end exactly as demo.py runs them, each checked against its
explicit expected answer (DEMO-01..DEMO-14 / the Assign06 table)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo import run_demo


class TestAllRequiredDemonstrations(unittest.TestCase):
    def test_every_demo_passes(self):
        rows, all_ok = run_demo(verbose=False)
        self.assertEqual(len(rows), 14)
        for row in rows:
            with self.subTest(demo=row["id"]):
                self.assertTrue(row["ok"], row)
        self.assertTrue(all_ok)

    def test_divergent_examples_report_exhaustion_not_a_value(self):
        rows, _ = run_demo(verbose=False)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["DEMO-09"]["exec_status"], "exhausted")
        self.assertEqual(by_id["DEMO-12"]["exec_status"], "exhausted")

    def test_terminating_examples_complete_within_documented_budget(self):
        rows, _ = run_demo(verbose=False)
        for row in rows:
            if row["id"] not in ("DEMO-09", "DEMO-12"):
                self.assertEqual(row["exec_status"], "completed", row["id"])


if __name__ == "__main__":
    unittest.main()
