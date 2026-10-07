# TESTING.md

Two layers of checks: **automated unit/integration tests** (Python `unittest`, 78 tests, no
browser) and an **automated browser smoke test** (Playwright driving headless Chromium, 32
checks). Both were run on 2026-10-07 on Linux with Python 3.12.3 and Flask 3.1.3; results below
are what was actually observed.

## How to run

```bash
python -m unittest discover -s tests -t .            # 78 tests, ~4 s
python tests/browser_smoke.py                        # needs requirements-dev.txt + a Chromium
```

If Playwright cannot find its own browser build, point it at any Chromium/Chrome binary with
`CHROMIUM_PATH=/path/to/chrome python tests/browser_smoke.py` (see README).

Observed: `Ran 78 tests ... OK`, and `RESULT: ALL CHECKS PASSED` for the browser run.

## Automated tests (what they cover)

| File | Covers (assignment task 4 item) |
| --- | --- |
| `tests/test_fvset.py` | (1) `d0exp_fvset` for every constructor, duplicate occurrences, nested bindings/shadowing, `fix` name+parameter, `let` initializer scope, unused bindings, result is a `frozenset`. |
| `tests/test_backend.py` | (2) Lint passes a closed program, lists names in sorted order for an open one, never calls `d0exp_evaluate` (patched to fail) and passes a closed `1/0` program that Interpret then fails. (3) Real interpretation of arithmetic, pairs, factorial (n = 0, 1, 5, 10), Fibonacci (n = 0, 1, 2, 10), malformed input, seven kinds of runtime failure (incl. `D0V000` directly and inside a pair), endless recursion. (5) Type-check/Compile are `NOT_IMPLEMENTED`, no artifact, Execute does not interpret. (6) A real timeout (`fib(32)` with a 1.5 s limit) and a crashing worker become `BACKEND_FAILURE`. |
| `tests/test_reader.py` | Restricted reader accepts nested/multiline/commented input; rejects `__import__`, `open`, attribute access, arithmetic, f-strings, starred args, wrong arity/types, `True` for an int, deep nesting, null bytes; the constructor table matches the `lambda1` dataclasses. |
| `tests/test_model.py` | (4) **Model-only tests, no browser or server:** manual input without upload, edit + apply, source replacement, rejection of empty/whitespace/oversize/invalid-UTF-8 input while keeping the previous source and the rejected draft, unapplied-edits and busy rules, artifact lifecycle, stale result dropped. |
| `tests/test_controller.py` | (5) Correct dispatch of each button to the matching backend operation using a **substituted `FakeBackend`** (view code unchanged, `present()` still works); placeholders never appear as success with the real backend; Execute stays unavailable. (6) Busy state blocks conflicting requests during a backend call and is released afterwards; backend exception → `BACKEND_FAILURE`, source preserved, **retry succeeds**; timeout-style failure then success; wrong-shaped backend result treated as failure; state readable from another thread while busy. |
| `tests/test_architecture.py` | Architectural boundaries from the import graph: model/controller/view do not import Flask, `lambda1`, the reader, the worker or the backend; only `web.py` builds the real backend; only reader/worker touch `lambda1`; the browser JS has no language logic. |
| `tests/test_web.py` | HTTP layer end to end with the real backend: page entries, CSP header, loopback host, factorial flow, open-expression flow, 409 rejections that preserve state, file upload (valid, invalid UTF-8, over limit, over HTTP body cap), HTML-like text returned unmodified. |

## Browser smoke test (`tests/browser_smoke.py`)

Procedure: the script starts the server on a free loopback port with `LAMBDA_UI_TIMEOUT=3`,
opens it in headless Chromium and performs the steps below in order. Each row lists the step,
the expected outcome (the check condition) and the value actually observed. All 32 checks passed.

| ID | Feature | Step / expected outcome | Observed (truncated) | Result |
| --- | --- | --- | --- | --- |
| B1 | F4 | five action buttons in the required order | `['Lint', 'Interpret', 'Type-check', 'Compile', 'Execute']` | PASS |
| B2 | F1 | Load source menu offers the four entries | `['Choose File', 'Manual input', 'Factorial (canned)', 'Fibonacci (canned)']` | PASS |
| B3 | F4 | all actions disabled before any source is applied | `[True, True, True, True, True]` | PASS |
| B4 | F1,F8 | canned example shows name and revision | `'Source: Factorial (canned) — revision 1'` | PASS |
| B5 | F1,F2 | canned example is loaded into the editable editor | `'# Factorial of 10 (expected: D'` | PASS |
| B6 | F6,F9 | Interpret factorial(10) shows value with action/revision/outcome | `(['Interpret · revision 1 · ✔ Success'], ['D0Vint(arg1=3628800)'])` | PASS |
| B7 | F2 | typing makes Apply/Discard available and disables actions and loading | `(False, True, 'Unapplied edits: press Ap')` | PASS |
| B8 | F2,F8 | Apply creates revision 2 and clears earlier results | `0` | PASS |
| B9 | F2,F6 | edited factorial(5) gives 120 | `['D0Vint(arg1=120)']` | PASS |
| B10 | F2 | Discard restores the applied source | `'# Factorial of 10 (e'` | PASS |
| B11 | F1,F6 | Fibonacci(10) = 55 | `['D0Vint(arg1=55)']` | PASS |
| B12 | F1,F2 | Manual input opens a blank editor and keeps the applied source for now | `'Source: Fibonacci (canned) — revision 3'` | PASS |
| B13 | F1,F8 | applied manual source named 'Manual input' with a new revision | `'Source: Manual input — revision 4'` | PASS |
| B14 | F5,F9 | Lint reports the undeclared variable as an error, in text | `('Lint · revision 4 · ✖ Language error', 'Undeclared variable(s): x')` | PASS |
| B15 | F5 | editing into a closed expression passes Lint | `('Lint · revision 5 · ✔ Success', 'No free variables found.')` | PASS |
| B16 | F5,F6 | closed program passes Lint but fails Interpret with a runtime error | `(['Interpret · revision 6 · ✖ Runtime error', 'Lint · revision 6 · ✔ Success'], 'Runtime error: ZeroDivisionError: in...` | PASS |
| B17 | F6 | malformed input is an Input error, distinct from Runtime error | `'Interpret · revision 7 · ✖ Input error'` | PASS |
| B18 | F3 | whitespace-only source is rejected; previous source kept; rejected text stays in editor | `'Error: Source is empty or contains only whitespace.'` | PASS |
| B19 | F1,F3 | invalid UTF-8 upload rejected; source unchanged | `('Error: File is not valid UTF-8 text.', 'Source: Manual input — revision 7')` | PASS |
| B20 | F3 | oversize upload rejected with the documented limit | `'Error: File exceeds the 65536-byte limit.'` | PASS |
| B21 | F1,F6 | Choose File uploads a UTF-8 file, shows its name/revision, and it interprets to 42 | `('Source: sum.txt — revision 8', 'D0Vint(arg1=42)')` | PASS |
| B22 | F7 | Type-check and Compile report 'not yet implemented', not success | `(['Compile · revision 8 · ℹ Not implemented', 'Type-check · revision 8 · ℹ Not implemented'], ['Compilation is not ye...` | PASS |
| B23 | F4,F7 | Execute stays disabled and the page explains why | `'Execute is disabled: Execute is for testing generated code produced by Compile. It is unavailable until compilation ...` | PASS |
| B24 | F9 | HTML-like source/output is shown literally (no markup elements created, no script effect) | `'Undeclared variable(s): <b>bold</b><img src=x onerror=document.title=1>'` | PASS |
| B25 | F9 | multi-line source with comments survives Apply with line breaks intact | `'# line1\n# line2\nD0Elet("x", D0Eint(1),\n    D0Evar("x"))'` | PASS |
| B26 | keyboard | load an example and run Interpret using only keyboard keys | `'D0Vint(arg1=3628800)'` | PASS |
| B27 | keyboard | Tab reaches editor and the enabled action buttons in page order | `['load-manual', 'load-factorial', 'load-fibonacci', 'editor', 'action-lint', 'action-interpret', 'action-typecheck', ...` | PASS |
| B28 | F10 | while a long run is in progress: busy status, controls disabled, page still responsive | `{'status': 'Busy: working…', 'actions_disabled': True, 'editor_readonly': True, 'load_disabled': True, 'responsive': ...` | PASS |
| B29 | F10 | the non-terminating/slow run is stopped by the timeout and reported as a tool failure | `('Interpret · revision 12 · ⚠ Tool failure', 'Timed out after 3 s; the worker was stopped. The program may not termin...` | PASS |
| B30 | F10 | controls restored and source preserved after the failure | `'Ready.'` | PASS |
| B31 | F10 | after the failure a retry on a quick program succeeds (fib(6)=8) | `'D0Vint(arg1=8)'` | PASS |
| B32 | F10 | when the server is unreachable the page says so and keeps the source | `'Error: could not reach the local server (Failed to fetch). Your source'` | PASS |

Notes on the run:

* A screenshot of the initial page was opened and inspected by eye (layout, labelled controls,
  dashed borders on disabled buttons). No other visual review was done; the checks above are
  DOM/text based.
* The harness creates its browser context with `bypass_csp=True` only so Playwright's own
  `wait_for_function` (which evaluates strings) is allowed. The page's real CSP header is asserted
  separately in `tests/test_web.py`. B24 therefore also proves literal rendering does not rely on
  the CSP: output is inserted with `textContent`.
* The first browser run exposed two problems: a real UI bug (a stale "OK: interpret finished"
  notice overwrote the "could not reach the local server" error in `static/app.js`, found by
  B32; fixed by routing the error through the view-model) and a race in the test's own wait
  condition (B10). Both were fixed and the whole script was rerun to produce the table above.
* B32 stops the server process, so it is intentionally the last check. Source text stays in the
  browser editor; because the model lives in server memory, reloading after a server restart
  starts with no applied source (documented limitation).

## Traceability: requirement -> checks

| ID | Automated tests | Browser checks |
| --- | --- | --- |
| F1 Load source menu, source name/revision | `test_web` (canned, upload, `test_index_and_headers`), `test_model` (manual, upload), `test_controller.SourceFlow` | B2, B4, B5, B12, B13, B19, B21 |
| F2 Edit, Apply/Discard, block while unapplied | `test_model` (edit/apply, unapplied-edits block, manual keeps applied source, no-op apply), `test_web` (409 while dirty, discard) | B5, B7, B8, B9, B10, B12 |
| F3 Reject empty/invalid/oversize, keep state | `test_model` (rejected changes, upload validation, byte limit), `test_web` (rejections, uploads) | B18, B19, B20 |
| F4 Button order, need applied source, Execute disabled | `test_model.OperationRules`, `test_controller.RealPlaceholders`, `test_web.test_factorial_end_to_end` | B1, B3, B23 |
| F5 Real Lint | `test_fvset` (all), `test_backend.LintTests`, `test_controller.test_load_lint_interpret_trace...` | B14, B15, B16 |
| F6 Real Interpret, input vs runtime errors | `test_backend.InterpretTests`, `test_web.test_factorial_end_to_end` | B6, B9, B11, B16, B17, B21 |
| F7 Type-check/Compile not implemented, Execute explained | `test_backend.PlaceholderTests`, `test_controller.RealPlaceholders` | B22, B23 |
| F8 New revision clears results/artifacts; rejects preserve | `test_model` (replacement, artifact lifecycle, rejected changes), `test_controller.ExecuteAndArtifacts` | B4, B8, B13 |
| F9 Textual results with action/revision/outcome; literal rendering | `test_controller.test_view_works_unchanged...`, `test_web` (title format, HTML-like passthrough), `test_backend.test_html_like...` | B6, B14, B24, B25 |
| F10 Busy status, retry, timeout, preserved source | `test_model.test_busy_blocks...`, `test_controller.FailuresBusyAndRetry`, `test_backend` (timeout, worker crash) | B28, B29, B30, B31, B32 |
| Keyboard / non-colour status (non-functional) | - | B26, B27 (keys only); status text and symbols in every result title (B6, B14, B22, B29) |
