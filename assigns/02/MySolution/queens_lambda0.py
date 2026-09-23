"""
queens_lambda0.py

Translates the ATS2 eight-queens solution (eightqueens.dats) into a
LAMBDA0 term and runs it with the extended t0erm_cbv_evaluate0
interpreter from lambda0.py.

USAGE:
    python3.12 queens_lambda0.py [N]

    N defaults to 8. Pass a smaller N (e.g. 4, 5, 6) for a fast run;
    N=8 takes roughly 1-2 minutes because the interpreter is
    substitution-based (see README "Limitations").

=====================================================================
DESIGN / MAPPING FROM ATS TO LAMBDA0  (see README.md for the full
narrative version of this section)
=====================================================================

ATS's `int8` (a fixed 8-tuple board) becomes a LAMBDA0 cons-list built
from T0Mpair, right-nested and terminated by a nil sentinel T0Mint(-1):

    (x0, (x1, (x2, ... (x_{N-1}, -1) ...)))

Column values are always >= 0 during search, so -1 is a safe, never-
colliding "nil" marker.

ATS's `board_get`/`board_set` (each a hardcoded 8-way if/elif chain,
since ATS tuples are fixed-size and not index-addressable at runtime)
become GENERIC recursive `list_get`/`list_set` functions written with
T0Mfix. This is a deliberate deviation from ATS's literal structure:
LAMBDA0's T0Mfix makes real recursion natural, so a generic walker is
both simpler and lets the same translation run at any board size N,
which the assignment explicitly allows for testing.

ATS's `safety_test1`/`safety_test2` translate directly: `abs` becomes
a small T0Mlam using T0Mif0, and ATS's `andalso` (short-circuiting
boolean and) becomes `T0Mif0(cond1, cond2, T0Mbtf(False))`, which has
the same short-circuit behavior.

ATS's `search(bd, i, j, nsol)` keeps its exact control flow (four
cases: place-and-descend, place-last-row-and-record, unsafe-try-next-
column, row-exhausted-backtrack) but its two ATS side effects --
printing a board and incrementing an integer counter -- are replaced
by ONE accumulator value, since the interpreter has no I/O:

    acc = (nsol, sols)

where `sols` is itself a cons-list of every solution board found, in
the same pair encoding as the board itself. This preserves both the
count (matching ATS's return value) and full enumeration (matching
ATS's printed output) in a single immutable result.

Every LAMBDA0 function used here (list_get, list_set, safety_test1,
safety_test2, search) is a CLOSED term -- it has no free variables --
so it is built once as a Python object and simply re-embedded
(spliced in by reference) everywhere it's called, rather than bound
with a "let". Recursive self-reference works because T0Mfix's own
substitution rule re-inserts the whole fix term for every self-call,
which is why every recursive call must re-supply ALL of that
function's curried arguments, including ones that didn't change
(this was the one real bug hit while building this translation --
see README "AI-assisted code review").
"""

import sys
from lambda0 import (
    T0Mvar, T0Mlam, T0Mfix, T0Mapp, T0Mint, T0Mbtf, T0Mstr,
    T0Mop1, T0Mop2, T0Mif0, T0Mpair, T0Mpfst, T0Mpsnd,
    t0erm_cbv_evaluate0,
)

NIL = T0Mint(-1)


def mk_list(values):
    """Python list of t0erm -> nil-terminated LAMBDA0 cons-list."""
    result = NIL
    for v in reversed(values):
        result = T0Mpair(v, result)
    return result


def unmk_list(term):
    """LAMBDA0 cons-list (already evaluated) -> Python list of t0erm."""
    out = []
    while isinstance(term, T0Mpair):
        out.append(term.arg1)
        term = term.arg2
    return out


def app(f, *args):
    for a in args:
        f = T0Mapp(f, a)
    return f


# ---------------------------------------------------------------
# list_get(lst, i): generic recursive index into a cons-list
# ---------------------------------------------------------------
list_get_term = T0Mfix(
    "list_get", "lst",
    T0Mlam("i",
        T0Mif0(
            T0Mop2("==", T0Mvar("i"), T0Mint(0)),
            T0Mpfst(T0Mvar("lst")),
            app(T0Mvar("list_get"), T0Mpsnd(T0Mvar("lst")),
                T0Mop2("-", T0Mvar("i"), T0Mint(1)))
        )
    )
)

# ---------------------------------------------------------------
# list_set(lst, i, v): generic recursive functional update
# ---------------------------------------------------------------
list_set_term = T0Mfix(
    "list_set", "lst",
    T0Mlam("i", T0Mlam("v",
        T0Mif0(
            T0Mop2("==", T0Mvar("i"), T0Mint(0)),
            T0Mpair(T0Mvar("v"), T0Mpsnd(T0Mvar("lst"))),
            T0Mpair(
                T0Mpfst(T0Mvar("lst")),
                app(T0Mvar("list_set"), T0Mpsnd(T0Mvar("lst")),
                    T0Mop2("-", T0Mvar("i"), T0Mint(1)), T0Mvar("v"))
            )
        )
    ))
)

# ---------------------------------------------------------------
# abs(x)
# ---------------------------------------------------------------
abs_term = T0Mlam("x",
    T0Mif0(
        T0Mop2("<", T0Mvar("x"), T0Mint(0)),
        T0Mop1("-", T0Mvar("x")),
        T0Mvar("x")
    )
)

# ---------------------------------------------------------------
# safety_test1(i0, j0, i1, j1) : bool
#   j0 != j1 andalso abs(i0-i1) != abs(j0-j1)
# ---------------------------------------------------------------
safety_test1_term = T0Mlam("i0", T0Mlam("j0", T0Mlam("i1", T0Mlam("j1",
    T0Mif0(
        T0Mop2("!=", T0Mvar("j0"), T0Mvar("j1")),
        T0Mop2("!=",
            app(abs_term, T0Mop2("-", T0Mvar("i0"), T0Mvar("i1"))),
            app(abs_term, T0Mop2("-", T0Mvar("j0"), T0Mvar("j1")))
        ),
        T0Mbtf(False)
    )
))))

# ---------------------------------------------------------------
# safety_test2(i0, j0, bd, i) : bool   (recursive, checks rows 0..i)
# ---------------------------------------------------------------
safety_test2_term = T0Mfix(
    "safety_test2", "i0",
    T0Mlam("j0", T0Mlam("bd", T0Mlam("i",
        T0Mif0(
            T0Mop2(">=", T0Mvar("i"), T0Mint(0)),
            T0Mif0(
                app(safety_test1_term, T0Mvar("i0"), T0Mvar("j0"),
                    T0Mvar("i"), app(list_get_term, T0Mvar("bd"), T0Mvar("i"))),
                # Recursive call must re-supply i0 -- every argument of a
                # curried T0Mfix, including unchanged ones -- since the
                # fix's self-name refers to the WHOLE curried function.
                app(T0Mvar("safety_test2"), T0Mvar("i0"), T0Mvar("j0"),
                    T0Mvar("bd"), T0Mop2("-", T0Mvar("i"), T0Mint(1))),
                T0Mbtf(False)
            ),
            T0Mbtf(True)
        )
    )))
)


def make_search_term(N):
    """search(bd, i, j, acc) -> acc, where acc = (nsol, sols)."""
    N_term = T0Mint(N)

    leaf_case = app(
        T0Mvar("search"),
        T0Mvar("bd"),
        T0Mvar("i"),
        T0Mop2("+", T0Mvar("j"), T0Mint(1)),
        T0Mpair(
            T0Mop2("+", T0Mpfst(T0Mvar("acc")), T0Mint(1)),
            T0Mpair(
                app(list_set_term, T0Mvar("bd"), T0Mvar("i"), T0Mvar("j")),
                T0Mpsnd(T0Mvar("acc"))
            )
        )
    )

    descend_case = app(
        T0Mvar("search"),
        app(list_set_term, T0Mvar("bd"), T0Mvar("i"), T0Mvar("j")),
        T0Mop2("+", T0Mvar("i"), T0Mint(1)),
        T0Mint(0),
        T0Mvar("acc")
    )

    try_next_col_case = app(
        T0Mvar("search"), T0Mvar("bd"), T0Mvar("i"),
        T0Mop2("+", T0Mvar("j"), T0Mint(1)), T0Mvar("acc")
    )

    backtrack_case = app(
        T0Mvar("search"), T0Mvar("bd"),
        T0Mop2("-", T0Mvar("i"), T0Mint(1)),
        T0Mop2("+", app(list_get_term, T0Mvar("bd"),
                        T0Mop2("-", T0Mvar("i"), T0Mint(1))), T0Mint(1)),
        T0Mvar("acc")
    )

    body = T0Mif0(
        T0Mop2("<", T0Mvar("j"), N_term),
        T0Mif0(
            app(safety_test2_term, T0Mvar("i"), T0Mvar("j"),
                T0Mvar("bd"), T0Mop2("-", T0Mvar("i"), T0Mint(1))),
            T0Mif0(
                T0Mop2("==", T0Mop2("+", T0Mvar("i"), T0Mint(1)), N_term),
                leaf_case,
                descend_case
            ),
            try_next_col_case
        ),
        T0Mif0(
            T0Mop2(">", T0Mvar("i"), T0Mint(0)),
            backtrack_case,
            T0Mvar("acc")
        )
    )

    return T0Mfix("search", "bd",
        T0Mlam("i", T0Mlam("j", T0Mlam("acc", body))))


def make_main_term(N):
    """Build the full closed term: search applied to the initial state."""
    bd0 = mk_list([T0Mint(0)] * N)
    init_acc = T0Mpair(T0Mint(0), NIL)
    search_term = make_search_term(N)
    return app(search_term, bd0, T0Mint(0), T0Mint(0), init_acc)


def solve(N):
    """Evaluate the N-queens term. Returns (nsol:int, boards:list[list[int]]).

    Runs in a worker thread with a raised recursion limit and a large
    OS stack, since this substitution-based interpreter recurses very
    deeply even for modest N (see README "Limitations").
    """
    import threading
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 200000))

    box = {}

    def run():
        term = make_main_term(N)
        result = t0erm_cbv_evaluate0(term)
        nsol = result.arg1.arg1
        boards = [[x.arg1 for x in unmk_list(b)] for b in unmk_list(result.arg2)]
        box["nsol"] = nsol
        box["boards"] = boards

    threading.stack_size(1 << 28)  # 256 MB
    th = threading.Thread(target=run)
    th.start()
    th.join()
    sys.setrecursionlimit(old_limit)
    return box["nsol"], box["boards"]


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(f"Solving {N}-queens with the LAMBDA0 translation...")
    nsol, boards = solve(N)
    print(f"Total number of solutions = {nsol}")
    for idx, b in enumerate(boards, start=1):
        print(f"\nSolution #{idx}: {b}")
