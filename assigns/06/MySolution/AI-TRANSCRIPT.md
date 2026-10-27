# AI-TRANSCRIPT.md

## Tools used

Claude (Anthropic), used as a coding assistant inside an agentic coding
session with file-editing and shell-execution tools, for the full
implementation: `names.py`, `target_ast.py`, `church.py`, `evaluator.py`,
`compiler.py`, `decoders.py`, `examples.py`, `demo.py`, the test suite
under `tests/`, and this documentation set (`README.md`, `DESIGN.md`,
this file).

## Important prompts and direction

The project was directed through a short sequence of prompts rather than
turn-by-turn micromanagement of each module:

1. The opening prompt supplied `Assign06.md` and `REQUIREMENTS.md` and
   asked for the full solution end to end: "build it so it passes ACC-01 through ACC-15 in REQUIREMENTS.md and show me each one passing as you go" This set the scope for
   everything that followed, and the AI was asked to flag anything it
   needed clarified rather than guess silently.
2. Two scoping questions were answered directly: `lambda1_vp.py` is the
   student's own Assignment 5 solution (not assignment-provided
   scaffolding), and the deliverable should be built as files in this
   session rather than pushed to a repository.
3. Asked for the hard design decisions explained before implementation, e.g. “before writing church.py, explain how predecessor and recursion will work under call-by-value, and why”. It was then signed off on the approach.
4. Asked for a risk pass before building, e.g. “what are the two or three trickiest correctness issues in this assignment, and how will you test for them specifically?" This surfaced the short-circuit and recursion-depth problems as a plan instead of as bugs found after the fact.
5. After the full solution was delivered, running the test suite locally
   (on the student's own machine, independently of this session)
   produced `SyntaxError: invalid syntax` on `type nint = int`. The exact
   terminal output — failing test names, error, and shell prompt — was
   captured and reported, and the follow-up prompt asked specifically how
   to run the project under Python 3.13 instead of the system default.
6. After applying that fix, the result was verified and reported back
   directly: "Both tests have passed with no errors."
7. A status check was requested next — "so what did you do, and tell me
   what I have to do yet, step by step" — to pin down exactly what
   remained (the slide deck, the video, and final submission steps).

## How testing and review actually happened

Verification happened on both sides, independently. On the AI's side,
every module was checked interactively against the assignment's own
worked examples before any automated test was written for it (see "How
the work was approached" below), and the full suite and demo script were
run to a clean pass before the solution was handed over. On the
student's side, the delivered code was not taken on faith — it was run
in a separate environment (the student's own machine) as a genuine
independent check, and that check is what caught the Python-version
incompatibility: this session's own Python 3.13 environment never
surfaced the `type`-statement syntax requirement, because it already
satisfied it. Only by running the exact same code somewhere else did the
dependency surface. After the fix, the suite was re-run and the passing
result was confirmed explicitly before the project was considered done,
rather than assuming the fix had worked.

## Design walkthrough and comprehension check

Before finalizing this document, the three riskiest design decisions —
the predecessor construction, the delayed-branch trick for `if`/`and`/
`or`, and the choice of `Z` over `Y` for `fix` — were walked through
directly with the student, who was asked to explain each one back or
flag anything that still felt like a black box, rather than simply
being told it was correct.

- **Predecessor.** The student accepted the "one step behind" framing
  but asked for a worked visual trace; a step-by-step table of the pair
  (0,0) → (0,1) → (1,2) → (2,3) → (3,4) was walked through to make the
  lag explicit.
- **Delayed branches.** The student independently and correctly
  explained the distinction in their own words — picking a branch
  returns a function value (a closure) without evaluating its body,
  while only an explicit application forces that body to run — which is
  exactly the property the `if`/`and`/`or` compilation relies on.
- **Z vs. Y.** The student agreed the two problems share the same shape
  but asked for more visual detail; a side-by-side reduction trace was
  given showing `Y F` forcing its own self-application forever before
  `F`'s body ever runs, against `Z F` hiding that same self-application
  behind a `lam v. ...`, which call-by-value treats as an already-done
  value and never looks inside — letting `F`'s body, and its base case,
  run immediately.

The student confirmed afterward that the explanation landed.

## How the work was approached

The assignment and requirements-specification documents
(`Assign06.md`, `REQUIREMENTS.md`) and the unmodified Assignment 5 source
(`lambda1_vp.py`) were supplied as the starting point. The implementation
was built and verified module by module, in the order suggested by the
assignment's own milestones:

1. `target_ast.py` (Term AST, printer, free variables, capture-avoiding
   substitution) — verified against the assignment's own ACC-01 example
   (`x := y` in `lam y. x` must produce an alpha-equivalent of
   `lam fresh. y`, with `y` remaining free) before moving on.
2. `church.py` (the encoding library) — every combinator checked to be
   closed (no free variables) immediately after writing it.
3. `evaluator.py`'s target-reduction path — checked against the
   assignment's own boundary cases (ACC-02 through ACC-04: zero-step
   values, left-to-right evaluation order with the outer application
   contracted last, exact budget-zero/budget-one behavior, determinism
   and input preservation) before anything was built on top of it.
4. Church arithmetic, comparisons, and booleans — decoded and checked
   against the corresponding Python operators across small ranges of
   inputs.
5. `evaluator.py`'s source-evaluation path (the extended language's own
   semantics, including `and`/`or` short-circuiting, `if0`, pairs, and
   `fix` including the coincident-binder case) — checked directly against
   hand-computed expected values, including the assignment's own
   `(fix f(f). f) 3 = 3` example.
6. `compiler.py` — checked against every one of the assignment's 14
   required end-to-end demonstrations, plus free-variable preservation on
   an open expression, plus explicit rejection tests for negative
   literals and unsupported operators (including inside unselected `if`
   branches and unapplied lambda bodies, since the compiler is fully
   compositional and visits everything).
7. `decoders.py` — the natural-number and boolean observers were
   initially built using an identity-combinator-based pair of boolean
   markers; testing against a non-boolean Church numeral revealed this
   choice let some non-boolean values collapse to a false "ok" decode
   (because repeatedly applying the identity function to a fixed marker
   is itself always the identity, regardless of how many times it is
   applied). The markers were switched to the `TRUE`/`FALSE` combinators
   themselves, which resolved this: a genuine Church boolean still
   decodes correctly by definition, and a non-boolean value such as a
   Church numeral now reliably produces a shape mismatch, reported as
   `"malformed"`, rather than a false positive.
8. `demo.py` — running all 14 required examples together initially
   crashed with a Python `RecursionError` on the two recursive examples
   (factorial of 4 and Fibonacci of 5), because the target reducer was
   written as directly-recursive Python calls, chaining one stack frame
   per beta-value step; several hundred to nearly two thousand steps
   exceeded Python's default recursion limit. The reducer was rewritten
   as an explicit stack machine (two frame kinds — "now evaluate the
   argument" and "now apply this function value") that performs the same
   sequence of beta-value steps without growing the Python call stack;
   after that change all 14 demonstrations passed, with step counts well
   inside the documented budgets (680 steps for factorial of 4, 1823 for
   Fibonacci of 5).
9. The automated test suite (`tests/`) was written after each module was
   individually verified as above, organized to map directly onto the
   assignment's seven numbered testing obligations and the
   requirements document's ACC-01 through ACC-15 acceptance criteria;
   it was run to a clean pass (117/117) as the last step before writing
   this file and `README.md`/`DESIGN.md`.

## Review and validation

Every module was exercised interactively (via short Python scripts run in
the development shell) against the assignment's own worked examples and
boundary cases before the corresponding automated test was written, so
each test in `tests/` encodes a check that had already been confirmed to
hold, rather than being written blind and trusted on the first run. The
two bugs described above (the boolean-marker choice and the recursion
depth in the reducer) were both found this way — by deliberately probing
edge cases beyond the assignment's literal demonstration table — rather
than by the required demonstrations themselves, which both bugs would
have passed undetected (the identity-marker bug does not affect any of
the 14 required demos, and the recursion-depth bug only surfaces once a
reduction runs into the hundreds of beta-value steps, which only the
recursive factorial/Fibonacci examples do). The full test suite
(`python3 -m unittest discover -s tests`) and the demonstration command
(`python3 demo.py`) were both run to completion, with their exit status
and output inspected, immediately before this submission was assembled.

Design choices that affect grading-relevant behavior — the predecessor
construction, the freshness policy, the choice of `Z` over `Y`, the
derivation of the comparison operators, and the budgets used in the demo
— are explained and justified in `DESIGN.md` and `README.md` rather than
repeated here.

## A better alternative approach

The process above worked, but in hindsight a more rigorous way to build
and verify this compiler would have been **differential (property-based)
testing**, rather than relying mainly on the 14 required demonstrations
plus a hand-picked set of unit tests chosen after manual inspection:

- Generate random, well-formed `D0Exp` source programs (bounded in size
  and recursion depth, so they stay inside the reduction budgets) using a
  tool such as Hypothesis.
- Evaluate each one two independent ways: directly, with the existing
  source-level evaluator (`eval_source`, built on `lambda1_vp.py`'s own
  AST and semantics); and through the full pipeline (`compile_expr`,
  then `eval_target`, then `observe_value`).
- Assert the two answers always agree, instead of only checking the
  specific examples a human happened to write by hand.

This single property — "compiling and reducing a program agrees with
evaluating it directly" — would have caught both bugs described above
(the boolean-marker collision in `decoders.py` and the reducer's
recursion-depth crash in `demo.py`) automatically, and most likely
earlier, without needing a human to notice the particular edge cases
that exposed them. It also gives the test suite coverage over the
*shape* of the language rather than a fixed list of examples, which is
closer to how compiler correctness is tested in practice.

A second improvement follows from how the recursion-depth bug was found:
only by crashing `demo.py` on the recursive examples, after the rest of
the implementation was already written. A more defensive design would
have anticipated unbounded reduction-step counts from the start — either
by writing the target reducer as an explicit stack machine in the first
draft (as it is now), or by representing target terms with De Bruijn
indices internally. The latter would also remove the need for the
`fresh_name`-based capture-avoidance logic inside `substitute`, at the
cost of a less directly readable printed form, which would then need a
separate name-reintroduction pass to satisfy TGT-02's printing
requirement. Named variables were kept here because printing is a
requirement of this assignment; De Bruijn indices are the more standard
choice when printing is not.
