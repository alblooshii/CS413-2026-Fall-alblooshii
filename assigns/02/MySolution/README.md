# Assignment 2 — Pairs/Projections and Eight-Queens in LAMBDA0

## 1. Extending `lambda0.py` with pairs and projections

`T0Mpair`, `T0Mpfst`, `T0Mpsnd` were added to all four core functions
in `lambda0.py`:

- **`t0erm_size`**: each pair/projection counts as 1 node plus the
  size of its subterm(s), matching the pattern already used for
  `T0Mop1`/`T0Mop2`.
- **`t0erm_fvset`**: free variables are the union of the components'
  free variables (for `T0Mpair`) or just the operand's (for
  `T0Mpfst`/`T0Mpsnd`). None of these constructors bind a variable, so
  no name is removed from the set.
- **`t0erm_subst0`**: substitution recurses into both pair components
  or the projection's operand, exactly like `T0Mop2`/`T0Mop1`. Since
  none of these constructors bind a name, there is no shadowing case
  to handle (unlike `T0Mlam`/`T0Mfix`).
- **`t0erm_cbv_evaluate0`**: this is the one place where care mattered.
  `T0Mpair(t1, t2)` evaluates `t1` **then** `t2` to values and returns
  the resulting pair — both components are always evaluated, even if
  a surrounding projection only wants one of them. `T0Mpfst`/`T0Mpsnd`
  evaluate their operand to a value; if it's a `T0Mpair`, they return
  the corresponding component, otherwise they raise `TypeError`.
  Because `T0Mpfst`/`T0Mpsnd` only ever look at the *already-evaluated*
  pair value, and `T0Mpair`'s own case is what forces both components
  eagerly, the required behavior
  (`T0Mpfst(T0Mpair(1, 1/0))` raises `ZeroDivisionError` rather than
  returning `1`) falls out automatically — no special-casing was
  needed in the projections themselves.

Tests for all four functions are in `TEST/test02_lambda0.py`, covering
the assignment's example assertions plus nested pairs/projections,
substitution under both `T0Mlam` and `T0Mfix` binders (including the
shadowing case where the bound name matches the substituted variable),
forced evaluation of both sides of a pair, mixed-type and
function-valued pairs, functions that take or return pairs, and the
`TypeError` case for projecting a non-pair.

## 2. Translating `eightqueens.dats` to LAMBDA0

The original ATS source is `eightqueens.dats` — an enumerate-and-count
backtracking solver (`search`) that places queens row by row, checks
each candidate against all previously placed queens
(`safety_test1`/`safety_test2`), and on success either recurses to the
next row or, if the last row was just placed, prints the board and
keeps searching the same row for further solutions.

### Data representation

ATS represents a board as `int8`, a fixed 8-tuple, with `board_get`/
`board_set` implemented as hardcoded 8-way `if`/`elif` chains, since
ATS tuples aren't index-addressable at runtime.

LAMBDA0 has no tuples, so a board of size N is represented as a
**cons-list built from `T0Mpair`**, right-nested and terminated by a
nil sentinel `T0Mint(-1)`:

```
(x0, (x1, (x2, ... (x_{N-1}, -1) ...)))
```

Column values are always ≥ 0 during search, so `-1` never collides
with a real value.

Rather than mirror ATS's fixed 8-case `board_get`/`board_set`, the
translation implements **generic recursive `list_get`/`list_set`**
functions using `T0Mfix`. This is a deliberate departure from ATS's
literal structure: LAMBDA0's `T0Mfix` makes real recursion natural
(ATS's fixed-size tuple couldn't be walked this way), and a generic
walker means the *same* translated program works at any board size N
— which is what lets `test03_queens.py` test N = 1 through 8 with one
implementation, as the assignment allows.

### Control logic

`safety_test1` and `safety_test2` translate directly. ATS's `abs` is
implemented as a small `T0Mlam` using `T0Mif0`. ATS's `andalso`
(short-circuiting boolean and) becomes `T0Mif0(cond1, cond2,
T0Mbtf(False))`, which has the same short-circuit behavior: `cond2` is
only evaluated when `cond1` is true.

`search(bd, i, j, nsol)` keeps ATS's exact four-way control flow
(place-and-descend / place-last-row-and-record / unsafe-try-next-
column / row-exhausted-backtrack), built with `T0Mfix` and curried
`T0Mlam`s for its four arguments.

### Replacing side effects: the accumulator

The interpreter has no I/O, so ATS's two side effects — printing each
solution board and incrementing an integer counter — are replaced by
a single accumulator value threaded through the recursion:

```
acc = (nsol, sols)
```

where `sols` is itself a cons-list of every solution board found so
far (same pair encoding as the board). This preserves both ATS's
return value (`nsol`, the count) and its printed output (every board,
via `sols`) in one immutable result, and lets `test03_queens.py` check
that every returned board is actually valid, not just count them.

### Primitive operations

No new primitives were needed. Comparisons (`<`, `>`, `>=`, `==`,
`!=`) were already implemented in the starter `t0erm_cbv_evaluate0`
and already produce `T0Mbtf` values as required.

## 3. Running it

```bash
# Extended interpreter tests (pairs/projections)
python3.12 TEST/test02_lambda0.py

# Quick sanity check of the queens translation (fast)
python3.12 queens_lambda0.py 4

# Full test suite for the queens translation (includes N=8, ~1-2 min)
python3.12 TEST/test03_queens.py
```

## 4. Results

`TEST/test03_queens.py` checks board sizes N = 1, 2, 3, 4, 5, 6, and
8 against the well-known correct queens-counting results, and
additionally validates every single returned board (no shared row,
column, or diagonal) and checks that all returned boards are
distinct.

| N | Solutions found | Known correct count |
|---|---|---|
| 1 | 1 | 1 |
| 2 | 0 | 0 |
| 3 | 0 | 0 |
| 4 | 2 | 2 |
| 5 | 10 | 10 |
| 6 | 4 | 4 |
| 8 | 92 | 92 |

All boards returned for every N were verified valid (no two queens
share a row, column, or diagonal) and mutually distinct. The N = 8
result, **92 solutions**, matches the original ATS program's
`Total number of solutions = 92` output (`eightqueens.dats`'s
`main0`). N = 7 was skipped in the automated suite purely to keep
total runtime reasonable; it is not a case the translation is
expected to handle any differently.

ATS/`patscc` was not installed in this environment, so the original
program was not recompiled and re-run side-by-side for this
assignment; the comparison instead uses the documented,
well-established correct solution counts for the N-queens problem,
which is exactly what running the ATS program is known to produce.

## 5. Call-by-value considerations

The interpreter is strictly call-by-value and substitution-based, and
one requirement of the assignment is that constructing a pair forces
*both* components even when a later projection only uses one. This
directly shaped the `T0Mpair` case in `t0erm_cbv_evaluate0` (see
section 1). It also means the `search` term can never accidentally
build an unevaluated/lazy board — every `list_set` call fully
evaluates the new board before it's threaded onward.

## 6. Limitations

The interpreter is **substitution-based**, not environment-based:
every function application re-substitutes the entire function body
(and, for recursive calls, re-substitutes the entire `T0Mfix` term for
its own name) rather than looking up a value in an environment. This
makes deeply recursive programs like N-queens require very deep
Python-level recursion. N = 8 requires raising Python's recursion
limit and running in a thread with a larger OS stack (both handled
automatically inside `queens_lambda0.solve()`), and still takes
roughly 1–2 minutes to complete — noticeably slower than a native
backtracking implementation would be, despite the algorithm itself
visiting only a couple of thousand search nodes. `test03_queens.py`
tests N = 1 through 6 quickly and N = 8 as the full case; this is
within what the assignment allows ("smaller board sizes where your
implementation supports").

## 7. AI-assisted code review

This translation was built with AI assistance and then reviewed and
tested rather than taken on faith, per the assignment's framing of
AI-generated code as a draft. Concretely:

- Every one of the four extended interpreter functions
  (`t0erm_size`, `t0erm_fvset`, `t0erm_subst0`,
  `t0erm_cbv_evaluate0`) was checked against the assignment's own
  example assertions before anything else was built on top of them,
  and `TEST/test02_lambda0.py` extends that coverage substantially
  further (nested terms, binder shadowing, forced evaluation order,
  mixed-value pairs, functions over pairs, the `TypeError` case).
- The eight-queens translation was tested incrementally — first N = 4
  (a small, hand-checkable case: exactly 2 known solutions), and only
  after that passed was N = 8 attempted.
- A real bug was caught this way: the first draft of `safety_test2`'s
  recursive self-call only re-supplied 3 of its 4 curried arguments
  (accidentally dropping `i0`, its own first parameter). Because
  `T0Mfix`'s recursive name refers to the *entire* curried function,
  a self-call must re-supply every argument on every recursive step,
  including ones that don't change between calls — omitting one
  silently produces a stuck, partially-applied value instead of a
  boolean, which surfaced immediately as a `TypeError` (`condition
  expects a boolean`) the first time N = 4 was run. The fix was to
  re-supply `i0` unchanged on every recursive call (see the comment
  at that call site in `queens_lambda0.py`).
- Once N = 4 produced the exact two known correct boards, N = 8 was
  run and its 92 solutions were independently checked for validity
  (no shared row/column/diagonal) and distinctness in
  `test03_queens.py`, rather than just trusting the solution count.
