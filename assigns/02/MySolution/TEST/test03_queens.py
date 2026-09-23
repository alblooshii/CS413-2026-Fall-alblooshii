"""
TEST/test03_queens.py

Tests for the LAMBDA0 translation of the ATS eight-queens program
(queens_lambda0.py). Run with:

    python3.12 TEST/test03_queens.py

Compares against the original ATS program's known, documented
behavior (eightqueens.dats prints every solution board and a final
"Total number of solutions = N" line via search()). Since ATS/patscc
was not installed in this environment (see README), the comparison
is against the well-established correct queens-counting results
(4-queens: 2 solutions, 5-queens: 10, 8-queens: 92), which is exactly
what running the compiled ATS program produces.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from queens_lambda0 import solve


def is_valid_board(cols, N):
    """No shared row (trivially true, one queen per row by construction),
    no shared column, no shared diagonal."""
    if len(cols) != N:
        return False
    if len(set(cols)) != N:  # no shared column
        return False
    for i in range(N):
        for j in range(i + 1, N):
            if abs(cols[i] - cols[j]) == abs(i - j):  # shared diagonal
                return False
    return True


def all_distinct(boards):
    return len(set(tuple(b) for b in boards)) == len(boards)


# --- Known correct solution counts (matches the original ATS program's
#     "Total number of solutions = " output for each board size) ---
KNOWN_COUNTS = {
    1: 1,
    2: 0,
    3: 0,
    4: 2,
    5: 10,
    6: 4,
}

print("Testing smaller board sizes against known correct counts...")
for N, expected in KNOWN_COUNTS.items():
    nsol, boards = solve(N)
    assert nsol == expected, f"N={N}: expected {expected} solutions, got {nsol}"
    assert len(boards) == expected, f"N={N}: nsol/boards length mismatch"
    assert all(is_valid_board(b, N) for b in boards), f"N={N}: invalid board found"
    assert all_distinct(boards), f"N={N}: duplicate boards found"
    print(f"  N={N}: {nsol} solutions, all valid and distinct -- OK")

print()
print("Testing conflict-checking logic directly...")

# A board with two queens sharing a column is invalid
assert not is_valid_board([0, 0, 1, 2], 4)
# A board with two queens on the same diagonal is invalid
assert not is_valid_board([0, 1, 2, 3], 4)
# A correct 4-queens solution is valid
assert is_valid_board([1, 3, 0, 2], 4)
print("  Conflict-checking helper: OK")

print()
print("Testing N=8 (the full eight-queens problem)...")
print("  (this takes roughly 1-2 minutes -- substitution-based interpreter,")
print("   see README 'Limitations')")
nsol8, boards8 = solve(8)
assert nsol8 == 92, f"expected 92 solutions for 8-queens, got {nsol8}"
assert len(boards8) == 92
assert all(is_valid_board(b, 8) for b in boards8), "invalid board found among 8-queens solutions"
assert all_distinct(boards8), "duplicate boards found among 8-queens solutions"
print(f"  N=8: {nsol8} solutions, all valid and distinct -- OK")
print("  This matches the original ATS program's "
      "'Total number of solutions = 92' output for eightqueens.dats.")

print()
print("ALL TESTS PASSED")
