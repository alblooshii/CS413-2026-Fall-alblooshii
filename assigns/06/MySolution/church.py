"""Task 2: Church-encoding library.

Every function here builds and returns a *closed* target Term (Var/Lam/App
only -- CMP-03, ENC-01). "TRUE", "PAIR", "Z", etc. are Python builder names,
not target-language primitives; calling them expands the abbreviation into
a pure term. Each call returns an independent, freshly-built tree, so
callers never need to worry about accidental sharing or mutation.

Representations (fixed by the assignment):

    TRUE     = lam t. lam f. t
    FALSE    = lam t. lam f. f
    NUM(n)   = lam s. lam z. s applied n times to z
    PAIR     = lam a. lam b. lam p. p a b
    Z        = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))
    I        = lam w. w

See DESIGN.md for the predecessor construction and the derivations of the
comparison operators.
"""
from __future__ import annotations

from target_ast import Term, Var, Lam, App


def I() -> Term:
    return Lam("w", Var("w"))


def TRUE() -> Term:
    return Lam("t", Lam("f", Var("t")))


def FALSE() -> Term:
    return Lam("t", Lam("f", Var("f")))


def NUM(n: int) -> Term:
    if n < 0:
        raise ValueError(f"Church numerals require n >= 0, got {n}")
    body: Term = Var("z")
    for _ in range(n):
        body = App(Var("s"), body)
    return Lam("s", Lam("z", body))


def PAIR() -> Term:
    return Lam("a", Lam("b", Lam("p", App(App(Var("p"), Var("a")), Var("b")))))


def FST() -> Term:
    return Lam("pr", App(Var("pr"), Lam("a", Lam("b", Var("a")))))


def SND() -> Term:
    return Lam("pr", App(Var("pr"), Lam("a", Lam("b", Var("b")))))


def Z() -> Term:
    # Z = lam g. (lam x. g (lam v. x x v)) (lam x. g (lam v. x x v))
    half = Lam(
        "x", App(Var("g"), Lam("v", App(App(Var("x"), Var("x")), Var("v"))))
    )
    return Lam("g", App(half, half))


def SUCC() -> Term:
    # lam n. lam s. lam z. s (n s z)
    return Lam(
        "n",
        Lam(
            "s",
            Lam("z", App(Var("s"), App(App(Var("n"), Var("s")), Var("z")))),
        ),
    )


def PRED() -> Term:
    # Kleene's pair-shifting predecessor (see DESIGN.md for the explanation):
    #   lam n. FST (n shifter (PAIR 0 0))
    #   shifter = lam p. PAIR (SND p) (SUCC (SND p))
    shifter = Lam(
        "p",
        App(
            App(PAIR(), App(SND(), Var("p"))),
            App(SUCC(), App(SND(), Var("p"))),
        ),
    )
    base = App(App(PAIR(), NUM(0)), NUM(0))
    return Lam("n", App(FST(), App(App(Var("n"), shifter), base)))


def ADD() -> Term:
    # lam m. lam n. n SUCC m   -- apply SUCC n times to m
    return Lam("m", Lam("n", App(App(Var("n"), SUCC()), Var("m"))))


def SUB() -> Term:
    # truncated subtraction: lam m. lam n. n PRED m
    return Lam("m", Lam("n", App(App(Var("n"), PRED()), Var("m"))))


def MUL() -> Term:
    # lam m. lam n. n (ADD m) (NUM 0)   -- apply "add m" n times to 0
    return Lam(
        "m", Lam("n", App(App(Var("n"), App(ADD(), Var("m"))), NUM(0)))
    )


def ISZERO() -> Term:
    # lam n. n (lam x. FALSE) TRUE
    return Lam("n", App(App(Var("n"), Lam("x", FALSE())), TRUE()))


def NOT() -> Term:
    # lam b. b FALSE TRUE
    return Lam("b", App(App(Var("b"), FALSE()), TRUE()))


def AND() -> Term:
    # lam p. lam q. p q FALSE  -- both operands are already-evaluated
    # Church booleans here (library-internal use, e.g. by EQ below); the
    # *source* "and" operator's short-circuit behavior is implemented by
    # the compiler's delayed-branch translation, not by this combinator.
    return Lam("p", Lam("q", App(App(Var("p"), Var("q")), FALSE())))


def OR() -> Term:
    # lam p. lam q. p TRUE q
    return Lam("p", Lam("q", App(App(Var("p"), TRUE()), Var("q"))))


def LEQ() -> Term:
    # m <= n  iff  (m - n) == 0, using truncated subtraction
    return Lam(
        "m", Lam("n", App(ISZERO(), App(App(SUB(), Var("m")), Var("n"))))
    )


def LT() -> Term:
    # m < n  iff  not (n <= m)
    return Lam(
        "m", Lam("n", App(NOT(), App(App(LEQ(), Var("n")), Var("m"))))
    )


def GT() -> Term:
    # m > n  iff  not (m <= n)
    return Lam(
        "m", Lam("n", App(NOT(), App(App(LEQ(), Var("m")), Var("n"))))
    )


def GEQ() -> Term:
    # m >= n  iff  n <= m
    return Lam("m", Lam("n", App(App(LEQ(), Var("n")), Var("m"))))


def EQ() -> Term:
    # m == n  iff  (m <= n) and (n <= m)
    return Lam(
        "m",
        Lam(
            "n",
            App(
                App(AND(), App(App(LEQ(), Var("m")), Var("n"))),
                App(App(LEQ(), Var("n")), Var("m")),
            ),
        ),
    )


def NEQ() -> Term:
    # m != n  iff  not (m == n)
    return Lam("m", Lam("n", App(NOT(), App(App(EQ(), Var("m")), Var("n")))))
