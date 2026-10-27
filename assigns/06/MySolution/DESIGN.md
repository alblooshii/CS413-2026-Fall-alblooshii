# DESIGN.md

## Translation rules

`C[e]` denotes the compiled target term for source expression `e`. `u`,
`v` denote fresh thunk parameters chosen per `names.fresh_name`, as
described below.

```
C[n]                    = NUM(n)                         (n >= 0)
C[true]                 = TRUE
C[false]                = FALSE
C[x]                    = x
C[lam x. e]              = lam x. C[e]
C[e1 e2]                 = C[e1] C[e2]
C[not e]                  = NOT C[e]
C[e1 + e2]                 = ADD C[e1] C[e2]
C[e1 - e2]                  = SUB C[e1] C[e2]              (truncated)
C[e1 * e2]                   = MUL C[e1] C[e2]
C[e1 < e2]                    = LT C[e1] C[e2]
C[e1 <= e2]                    = LEQ C[e1] C[e2]
C[e1 > e2]                      = GT C[e1] C[e2]
C[e1 >= e2]                      = GEQ C[e1] C[e2]
C[e1 == e2]                       = EQ C[e1] C[e2]
C[e1 != e2]                        = NEQ C[e1] C[e2]
C[if c then t else f]               = (C[c] (lam u. C[t]) (lam v. C[f])) I
C[e1 and e2]                         = (C[e1] (lam u. C[e2]) (lam v. FALSE)) I
C[e1 or e2]                           = (C[e1] (lam u. TRUE) (lam v. C[e2])) I
C[let x = e1 in e2]                    = (lam x. C[e2]) C[e1]
C[pair e1 e2]                           = PAIR C[e1] C[e2]
C[fst e]                                 = FST C[e]
C[snd e]                                  = SND C[e]
C[fix f(x). e]                             = Z (lam f. lam x. C[e])
```

`I`, `Z`, and every named combinator (`NOT`, `ADD`, ..., `PAIR`, `FST`,
`SND`) are expanded into pure `Var`/`Lam`/`App` terms by `church.py`; none
of these names survive into compiler output.

## Predecessor construction

`PRED` uses Kleene's classic pair-shifting trick, since a Church numeral
only supports iterating a function `n` times — it has no direct way to
"peel off" one successor. The idea: iterate a *pair-shifting* function `n`
times starting from `(0, 0)`, where each iteration replaces `(a, b)` with
`(b, b+1)`:

```
shifter = lam p. PAIR (SND p) (SUCC (SND p))
PRED    = lam n. FST (n shifter (PAIR 0 0))
```

After `k` iterations starting from `(0, 0)`, the pair holds `(k-1, k)`
for `k >= 1` and `(0, 0)` for `k = 0`. Taking `FST` of the result after
`n` iterations therefore yields `n - 1` for `n >= 1`, and `0` for `n = 0`
— predecessor of zero is zero, as required, for free, without a special
case.

## Comparisons

`LEQ m n = ISZERO (SUB m n)`, using truncated subtraction (`m <= n` iff
`m - n = 0`). The rest are derived rather than built as independent
fixed-points, to keep the library small and keep each operator's
correctness traceable to `LEQ`/`SUB`/`ISZERO`:
`LT m n = NOT (LEQ n m)`, `GT m n = NOT (LEQ m n)`, `GEQ m n = LEQ n m`,
`EQ m n = AND (LEQ m n) (LEQ n m)`, `NEQ m n = NOT (EQ m n)`. The `AND`
used here is a plain Church-boolean combinator (`lam p. lam q. p q
FALSE`) operating on two *already-evaluated* Church booleans — it is not
the short-circuiting translation used for the source `and`/`or`
operators (see below), and no divergence concern arises here because its
operands are always the result of comparing two already-available Church
numerals, which always terminates.

## Freshness policy

Most binders in compiled output directly echo a source-given name (`lam
x. e`'s `x`, `let x = ...`'s `x`, a `fix f(x)`'s `f` and `x`) — these need
no freshening, because capture-avoidance is substitution's job (see
below), not the compiler's. The only binders the compiler itself invents
are the `u`/`v` thunk parameters used to delay a branch until it is
selected. Each is chosen with `names.fresh_name(base, avoid)`: try `base`
itself (`"u"` or `"v"`); if it is already free in the branch it will wrap,
try `base_1`, `base_2`, ... in order, taking the first unused name. `u` is
chosen fresh against the free variables of *only* the branch it wraps
(the "then" branch, or the first operand's continuation for `and`), and
likewise `v` against its own branch — each thunk parameter's scope is
local to its own branch, so the two choices cannot interfere with each
other even if they coincide. This never reserves "plain" names like `s`,
`z`, `t`, `f`, or `x` for compiler use; they are only avoided on the rare
occasions they actually collide with a thunk parameter, and a fresh-name
check against a small, locally-scoped free-variable set keeps that
occasion rare and the resulting names short in practice.

## Evaluation strategy

Both the source and target evaluation paths implement left-to-right
call-by-value, and they live in one module (`evaluator.py`) behind one
entry point, `evaluate`. The source path is a conventional
environment/closure interpreter, written directly against this project's
extended source language (it is not `lambda1_vp.EvaluateVisitor`, which
predates `and`/`or`/`not`/pairs/`fix`). The target path is pure
substitution-based term rewriting with no notion of environment at all —
`(lam x. body) v --> body[x := v]` — under an explicit, finite beta-value
step budget. A beta step is only ever performed when both the function
and the argument subterms have already been reduced to values (`Lam`
nodes); reduction never looks inside a `Lam`'s body, so a lambda is
always a value in zero steps however many redexes it conceals. This
single asymmetry — source evaluation unbounded, target evaluation
budgeted — mirrors the assignment's own requirement that source-side
evaluation need not be step-bounded while target execution must be.

One implementation detail worth recording: the target reducer is written
as an explicit stack machine (two frame kinds, "evaluate the argument
next" and "apply this function value"), not as directly-recursive Python
function calls. A direct recursive implementation is simpler to read but
chains one Python stack frame per beta-value step; the required
recursive-factorial and Fibonacci demonstrations need several hundred to
nearly two thousand steps respectively, which exceeded Python's default
recursion limit during development. The stack-machine version performs
identically many beta-value steps and produces identical results — it
differs only in using a Python `list` instead of the Python call stack to
track pending work.

## Correctness claim and argument

**Claim.** For a closed, well-typed program `e` in the source language
specified here that evaluates (under the source semantics) to a natural
number, boolean, or finite nested pair of such values, observing
`eval_target(C[e], budget)` with a sufficiently large budget, under the
observer for `e`'s expected result kind, yields the same data.

The argument proceeds by structural cases, relying on two facts proved
separately: (1) compilation preserves free variables, `FV(C[e]) = FV(e)`
(immediate by induction on the translation rules above, since every
compiler-introduced binder is either a direct copy of a source binder or
a thunk parameter chosen fresh against exactly the free variables it
could otherwise capture); and (2) `substitute` is genuinely
capture-avoiding (renaming a bound variable whenever leaving it alone
would let a substituted-in free variable be captured). Given these,
**application** and **let** translate directly as applications/lets of
the translated subterms, so beta-reduction on the target side simulates
substitution on the source side one-for-one. **Conditionals** (and the
short-circuiting `and`/`or`) are the one place where naive compositional
translation would be wrong: if `C[if c then t else f]` were simply
`C[c] C[t] C[f]`, call-by-value would evaluate *both* `C[t]` and `C[f]`
before ever consulting `C[c]`, which is observably different from the
source semantics whenever one branch diverges or errors — exactly the
case the assignment calls out (`(lam x. 0) LOOP` must exhaust the budget,
while `if true then 1 else LOOP` must return `1`). Wrapping each branch
in a thunk (`lam u. C[t]`, `lam v. C[f]`) and forcing only the one the
Church boolean selects, via the trailing `I`, defers evaluation of the
unselected branch indefinitely — it is never applied, so it is never
reduced. **Recursion** uses `Z`, a call-by-value fixed-point combinator,
rather than the textbook `Y`, because `Y`'s self-application happens
*before* the function body can productively use its argument, so under
call-by-value `Y f` diverges immediately even for a terminating `f`; `Z`
delays that self-application behind an extra lambda (`lam v. x x v`), so
it only unfolds once applied to an actual argument, which is exactly
when a call-by-value recursive call is supposed to make progress.

**Limits of testing.** The test suite checks finitely many representative
cases — scope and shadowing, every operator, every comparison outcome,
every boolean truth-table row, several recursive programs, and the
required demonstrations — but finitely many passing tests can never prove
the translation correct for all programs; they can only fail to find a
counterexample among the cases chosen. In particular, the test suite
cannot exercise every possible name-collision pattern between source
identifiers and compiler-introduced thunk parameters, nor every depth of
nested recursion; the free-variable-preservation and
compositionality arguments above exist precisely because they generalize
where enumeration cannot.

## Design tradeoffs

Deriving `LT`/`GT`/`GEQ`/`EQ`/`NEQ` from `LEQ` rather than encoding each
independently keeps the library small and each operator's correctness
easy to state, at the cost of each derived comparison needing a few more
beta-value steps than a hand-optimized direct encoding would. Given the
assignment's budgets are generous and none of the required examples come
close to exhausting them, this traded a small, constant per-comparison
step overhead for a shorter, more obviously correct library. Likewise,
`substitute` rebuilds the (small) part of a term's structure it touches
rather than mutating in place; terms are frozen dataclasses throughout,
which makes "do not mutate the input" trivially true by construction
rather than something that has to be checked.
