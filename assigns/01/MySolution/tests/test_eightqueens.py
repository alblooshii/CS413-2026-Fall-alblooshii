"""
Tests for eightqueens.py, comparing its behavior against the
documented behavior of the original ATS program (eightqueens.dats).

Note: ATS (patscc) was not available in this environment to compile
and run the original program directly. Instead, these tests compare
against the exact outputs documented in the source material
(the ATS textbook chapter the professor provided), which describes:
  - the output of print_board on a specific board configuration
  - the first solution found by search()
  - the total number of solutions (92)
"""

import io
import sys
import unittest

sys.path.insert(0, "..")
import eightqueens as eq


def capture_output(func, *args, **kwargs):
    """Run func, capturing everything it prints to stdout."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        result = func(*args, **kwargs)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    return result, output


class TestNormalCase(unittest.TestCase):
    """
    Normal input case: print_board on the identity-diagonal board
    (0,1,2,3,4,5,6,7). This is the example given directly in the
    professor's documentation and has a fully deterministic,
    documented expected output.
    """

    def test_print_board_diagonal(self):
        expected = (
            "Q . . . . . . . \n"
            ". Q . . . . . . \n"
            ". . Q . . . . . \n"
            ". . . Q . . . . \n"
            ". . . . Q . . . \n"
            ". . . . . Q . . \n"
            ". . . . . . Q . \n"
            ". . . . . . . Q \n"
            "\n"
        )
        _, output = capture_output(eq.print_board, (0, 1, 2, 3, 4, 5, 6, 7))
        self.assertEqual(output, expected)


class TestBoundaryCase(unittest.TestCase):
    """
    Boundary/unusual case: board_get and board_set at the very first
    (i=0) and very last (i=7) row indices, and board_get with an
    out-of-range index (which the original ATS defines to return -1).
    """

    def test_board_get_first_and_last_row(self):
        bd = (5, 1, 2, 3, 4, 6, 0, 7)
        self.assertEqual(eq.board_get(bd, 0), 5)
        self.assertEqual(eq.board_get(bd, 7), 7)

    def test_board_get_out_of_range_returns_negative_one(self):
        bd = (0, 0, 0, 0, 0, 0, 0, 0)
        # matches the ATS `else ~1` fallback branch in board_get
        self.assertEqual(eq.board_get(bd, 8), -1)
        self.assertEqual(eq.board_get(bd, -1), -1)

    def test_board_set_preserves_other_rows(self):
        bd = (0, 0, 0, 0, 0, 0, 0, 0)
        updated = eq.board_set(bd, 3, 5)
        self.assertEqual(updated, (0, 0, 0, 5, 0, 0, 0, 0))


class TestFullSearch(unittest.TestCase):
    """
    Full run of search(), compared against the documented behavior
    of the original ATS program:
      - exactly 92 total solutions
      - the first solution printed matches the exact board shown
        in the professor's documentation
    """

    def test_total_solution_count_matches_documented_92(self):
        bd0 = (0, 0, 0, 0, 0, 0, 0, 0)
        nsol, _ = capture_output(eq.search, bd0, 0, 0, 0)
        self.assertEqual(nsol, 92)

    def test_first_solution_matches_documented_output(self):
        expected_first_solution = (
            "Solution #1:\n"
            "\n"
            "Q . . . . . . . \n"
            ". . . . Q . . . \n"
            ". . . . . . . Q \n"
            ". . . . . Q . . \n"
            ". . Q . . . . . \n"
            ". . . . . . Q . \n"
            ". Q . . . . . . \n"
            ". . . Q . . . . \n"
            "\n"
        )
        bd0 = (0, 0, 0, 0, 0, 0, 0, 0)
        _, output = capture_output(eq.search, bd0, 0, 0, 0)
        # only check that the output *starts* with the first solution block
        self.assertTrue(output.startswith(expected_first_solution))


class TestSafetyFunctions(unittest.TestCase):
    """
    My own additional tests: directly exercising safety_test1 and
    safety_test2, the core correctness logic of the puzzle (same
    row/column/diagonal attack detection).
    """

    def test_safety_test1_detects_same_column(self):
        self.assertFalse(eq.safety_test1(0, 3, 1, 3))  # same column

    def test_safety_test1_detects_diagonal_attack(self):
        self.assertFalse(eq.safety_test1(2, 2, 4, 4))  # same diagonal

    def test_safety_test1_allows_safe_position(self):
        self.assertTrue(eq.safety_test1(0, 0, 1, 2))  # not same col/diagonal

    def test_safety_test2_all_clear_on_empty_rows_above(self):
        bd = (0, 0, 0, 0, 0, 0, 0, 0)
        # i = -1 means "no rows above to check" -> vacuously safe
        self.assertTrue(eq.safety_test2(5, 5, bd, -1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
