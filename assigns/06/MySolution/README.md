# CS413 Midterm 1 — Compiling Extended LAMBDA into Pure Lambda-Calculus

## Requirements

* Python 3.12 or later (developed and tested on Python 3.13). No
  third-party dependencies — the standard library only.

## Layout

```
assigns/
  05/
    lambda1_vp.py        unmodified Assignment 5 source AST + D0ExpVisitor
  06/
    MySolution/
      names.py            deterministic fresh-name policy
      target_ast.py        Task 1: Term AST (Var/Lam/App), printer, free
                            variables, capture-avoiding substitution
      church.py              Task 2: Church-encoding library
      evaluator.py              the single shared evaluator (source AST
                                 path + target-term path)
      compiler.py                Task 3: compile_expr (D0ExpVisitor)
      decoders.py                  Task 4: observe_nat / observe_bool /
                                    observe_value (pairs)
      examples.py                   the 14 required source-program
                                     examples, shared by demo.py and the
                                     tests
      demo.py                        Task 4 demonstration command
      tests/                          automated unittest suite
      README.md, DESIGN.md, AI-TRANSCRIPT.md
```

Every module above imports `lambda1_vp` by locating
`assigns/05/lambda1_vp.py` relative to its own file location (not relative
to the current working directory), so the commands below work from any
directory, though `assigns/06/` is the documented one.

## Running the tests

From `assigns/06/`:

```
python3 -m unittest discover -s MySolution/tests -v
```

117 tests, all passing as of this submission. Runtime: a few seconds.

## Running the demonstration

From `assigns/06/`:

```
python3 MySolution/demo.py
```

This compiles, executes, and decodes all 14 required examples
(DEMO-01..DEMO-14 / Assign06's Task 4 table) and prints, for each: the
source description, the generated pure term (or, for the two recursive
examples whose printed term is long, the path of a saved `.txt` file
under `MySolution/generated_terms/`), the execution status and beta-value
step count, the observation status and step count, the decoded answer,
and the explicit expected answer, with a final `PASS`/`FAIL` per example.
The command exits 0 if every example matches its expected result.

## Budgets

Three budgets are used, each documented at the top of `demo.py` and
passed explicitly wherever a beta-value reduction happens:

* **Execution budget — 200,000 steps.** The budget used to reduce a
  compiled program to a value. During development, the largest
  terminating required example (recursive factorial applied to 4)
  measured 680 steps, and recursive Fibonacci applied to 5 measured 1823
  steps, so 200,000 leaves roughly two orders of magnitude of margin.
* **Divergence budget — 2,000 steps.** Used only for the two examples
  that are required to exhaust their budget (`(lam x. 0) LOOP` and
  `LOOP` itself). Any finite budget demonstrates exhaustion for a
  genuinely divergent program; this one is kept small so the
  demonstration finishes quickly rather than spinning for 200,000 steps
  on a program known never to terminate.
* **Observation budget — 2,000 steps.** The separate budget for the
  observation-stage reduction: applying an already-reduced value to the
  `STEP`/`BASE` natural-number probe, to the two boolean markers, or
  (recursively, for pairs) to `FST`/`SND` and then to one of the above.
  Every required example decodes in under 70 observation steps.

These are not universal correctness thresholds — they are simply
generous enough for the required demonstrations and the test suite, and
can be raised by the caller for larger programs (`eval_target`,
`observe_nat`, `observe_bool`, and `observe_value` all take the budget as
an explicit argument; nothing is hard-coded inside the compiler or
evaluator).

## Status and diagnostic representations

* **Target reduction** (`evaluator.eval_target`) returns a `TargetResult`
  with `status` in `{"completed", "exhausted"}`, the resulting `term`
  (a value if completed; the not-yet-contracted redex if exhausted), and
  the number of beta-value `steps` actually performed. A closed value
  completes in zero steps; evaluating an **open** target term raises
  `evaluator.EvalError` immediately, rather than silently continuing —
  target execution is restricted to closed terms (see DESIGN.md).
* **Source evaluation** (`evaluator.eval_source`) is unbounded, per the
  assignment ("source-side evaluation is required only for terminating
  examples and need not be step-bounded"), and returns a `SourceValue`
  (`SInt`/`SBool`/`SPair`/a closure) or raises `evaluator.EvalError` for a
  genuine evaluation-time error (unbound variable, wrong-type operand,
  applying a non-function).
* **Compilation** (`compiler.compile_expr`) raises `compiler.CompileError`
  for a negative literal or an unsupported operator spelling, with a
  message naming the offending literal or operator. Because compilation
  is fully compositional, every subexpression is visited regardless of
  whether it is ever dynamically reached, so this check applies uniformly
  to unselected `if`/`and`/`or` branches and to unapplied lambda bodies.
* **Decoders** (`decoders.observe_nat`, `observe_bool`, `observe_value`)
  return an `ObserveResult` with `status` in
  `{"ok", "exhausted", "malformed"}`. `"malformed"` means the observed
  value's shape did not match the expected kind (e.g. applying the
  natural-number probe to something that isn't a two-level
  lambda-of-lambda numeral spine); `"exhausted"` means a reduction budget
  (execution or observation) ran out before a definite shape could be
  determined. The two are always distinguishable in the returned
  `status`, and a `"malformed"` result is never reported as a decoded
  answer.

## Module overview

* **`names.py`** — one function, `fresh_name(base, avoid)`: the
  deterministic freshness policy used wherever the compiler needs to
  introduce a binder that is not simply echoing a source-given name (the
  `u`/`v` thunk parameters for delayed branches). See DESIGN.md.
* **`target_ast.py`** — `Var`/`Lam`/`App` (frozen dataclasses, so no
  operation here can mutate a term), `free_vars`, `substitute`
  (capture-avoiding, renaming via `names.fresh_name` only when a real
  capture hazard exists), `print_term` (the exact TGT-02 format), and
  `alpha_equivalent` (used by the decoders and the tests, not by the
  reducer itself).
* **`church.py`** — every Church-encoding combinator as a function
  returning a freshly-built, closed `Term`. See DESIGN.md for the
  predecessor construction and the derivation of the comparison
  operators from truncated subtraction.
* **`evaluator.py`** — the single shared evaluator. `evaluate(node, env=,
  budget=)` dispatches on whether `node` is a target `Term` (bounded,
  substitution-based reduction, implemented as an explicit stack machine
  rather than recursively — see DESIGN.md) or a source AST node
  (unbounded, environment/closure-based). Both paths live in this one
  module; it never imports `compiler.py`.
* **`compiler.py`** — `compile_expr`, a `D0ExpVisitor[Term]`
  implementation. Every translation rule is listed in the module
  docstring and restated with its justification in DESIGN.md.
* **`decoders.py`** — `observe_nat`, `observe_bool`, and `observe_value`
  (which runs the full execute-then-decode pipeline and recurses for
  pairs).
* **`examples.py`** — the 14 required example programs, built directly as
  `D0E...` AST nodes (no parser is used or required).
* **`demo.py`** — runs every example in `examples.py` through the full
  pipeline and prints the required report.

## Known limitations

* No source parser; examples are Python-constructed ASTs, as the
  assignment allows.
* The target reducer is a tree-walking interpreter over immutable terms
  (substitution copies the parts of the term it rewrites); it is not
  optimized for large programs, though the explicit-stack design means it
  does not hit Python's recursion limit even for reductions with
  thousands of beta-value steps (recursive factorial/Fibonacci were the
  stress tests during development).
* `observe_bool`'s malformed-detection (and `observe_nat`'s) is "best
  effort": the assignment explicitly does not require recognizing every
  invalid untyped encoding, and a sufficiently adversarial non-boolean or
  non-numeral value could in principle alpha-reduce to something that
  coincidentally matches the expected shape.
