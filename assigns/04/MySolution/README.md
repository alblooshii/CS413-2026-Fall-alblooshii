# LAMBDA Workbench: a Model–View–Controller web front-end

Load or type a LAMBDA program (as a Python `d0exp` constructor expression), **Lint** it
(real free-variable check), **Interpret** it (real `d0exp_evaluate`), and read the textual
result in the browser. Type-check, Compile and Execute are present as honest placeholders.

Documents: [ARCHITECTURE.md](ARCHITECTURE.md) (MVC design, diagrams, backend contract) ·
[TESTING.md](TESTING.md) (automated + browser results, traceability to F1–F10) ·
[AI-TRANSCRIPT.md](AI-TRANSCRIPT.md).

## Requirements and setup

* Python **3.12 or later** (`lambda1.py` uses the `type` statement). Developed with 3.12.3.
* Flask 3.x (the only runtime dependency, declared in `requirements.txt`; the 3.1.3 release was used).
* A modern desktop browser (the browser test used headless Chromium).

From this directory (`assigns/04/MySolution`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python -m lambda_ui                    # optional: --port 5001
```

Then open **http://127.0.0.1:5000/**. The server binds to the loopback interface only.
Stop it with Ctrl+C.

## Run the tests

```bash
python -m unittest discover -s tests -t .          # 78 automated tests, no browser needed, ~4 s
```

Browser smoke test (32 checks, optional extra dependencies):

```bash
pip install -r requirements-dev.txt
playwright install chromium                         # one-time browser download
python tests/browser_smoke.py
# If Playwright cannot find its browser build, use any local Chrome/Chromium:
#   CHROMIUM_PATH=/path/to/chrome python tests/browser_smoke.py
```

## Using the page

1. **Load source**: *Choose File* (UTF-8 text file), *Manual input* (blank editor),
   *Factorial (canned)*, *Fibonacci (canned)*. The page shows the source name and revision.
2. Edit in the editor. **Apply changes** makes the text the application's copy (a new revision);
   **Discard changes** restores the applied text. While edits are unapplied, actions and loading
   are disabled. Edits never modify the original local file.
3. Press **Lint**, **Interpret**, **Type-check**, **Compile** or **Execute** (in that order on the page).
   Each result is listed with its action, revision and outcome; results belong to one revision and
   are cleared when a new revision is created.

## Demonstration (every output below was produced by the running application)

1. **Factorial and Fibonacci.** Click *Factorial (canned)* → *Interpret*:
   `Interpret · revision 1 · ✔ Success` / `D0Vint(arg1=3628800)`. To change the input, edit the last
   line (`D0Eint(10)` → `D0Eint(5)`), *Apply changes* (revision 2), *Interpret*: `D0Vint(arg1=120)`.
   *Fibonacci (canned)* → *Interpret*: `D0Vint(arg1=55)`. The canned original is untouched:
   loading it again restores the original text.
2. **Open expression, then fixed.** *Manual input*, type `D0Evar("x")`, *Apply changes*, *Lint*:
   `Lint · revision N · ✖ Language error` / `Undeclared variable(s): x`. Edit to
   `D0Elet("x", D0Eint(1), D0Evar("x"))`, *Apply changes*, *Lint*: `✔ Success` /
   `No free variables found.`
3. **Runtime failure after a successful Lint.** Apply `D0Eop2("/", D0Eint(1), D0Eint(0))`.
   *Lint*: `✔ Success` (the expression is closed; Lint never evaluates). *Interpret*:
   `✖ Runtime error` / `Runtime error: ZeroDivisionError: integer division or modulo by zero`.
   Lint answers "is the expression closed?"; Interpret answers "does evaluation succeed?".
   A malformed expression shows `✖ Input error` instead, so the three failure kinds look different.
4. **Placeholders.** *Type-check*: `ℹ Not implemented` / `Type checking is not yet implemented.`
   *Compile*: `ℹ Not implemented` / `Compilation is not yet implemented. Execute runs code produced
   by Compile, so it stays unavailable until compilation exists and has produced an artifact.`
   *Execute* stays disabled and the page says: "Execute is for testing generated code produced by
   Compile. It is unavailable until compilation is implemented and has produced an artifact for the
   current revision."

More inputs are in `samples/` (`factorial.txt`, `fibonacci.txt`, `arithmetic.txt`,
`error_open_variable.txt`, `error_closed_version.txt`, `error_division_by_zero.txt`,
`error_malformed.txt`, `error_html_like.txt`); load them with *Choose File*.

## Supported input format

The source is **one Python constructor expression of type `d0exp`**, with constructor names
available without imports: `D0Eint(int)`, `D0Ebtf(bool)`, `D0Evar(str)`, `D0Eop1(str, exp)`,
`D0Eop2(str, exp, exp)`, `D0Elam(str, exp)`, `D0Efix(str, str, exp)`, `D0Eapp(exp, exp)`,
`D0Eif0(exp, exp, exp)`, `D0Elet(str, exp, exp)`, `D0Epair(exp, exp)`, `D0Epfst(exp)`,
`D0Epsnd(exp)`. Nested constructors, `#` comments and multi-line expressions are accepted;
negative integer literals (`D0Eint(-3)`) and keyword arguments by field name are accepted.

Example: `D0Eop2("+", D0Eint(20), D0Eint(22))`.

The text is parsed with `ast.parse` and walked by a restricted reader (`lambda_ui/reader.py`);
**nothing is ever passed to `eval` or `exec`**. Anything that is not a whitelisted constructor
applied to correctly typed literals/sub-expressions (function calls, attributes, arithmetic,
imports, variables, `True` where an int is expected, wrong arity, nesting deeper than 200) is an
*Input error*. Operator names are not validated by the reader: an unsupported operator is a
*Runtime error* when evaluation reaches it.

## Execution bounds and limits

| Limit | Value |
| --- | --- |
| Source size | 64 KiB (65 536 UTF-8 bytes) |
| Upload encoding | UTF-8 (a leading BOM is accepted) |
| Per-operation timeout | 5 s default; `LAMBDA_UI_TIMEOUT=<seconds> python -m lambda_ui` to change. On timeout the worker process is killed and a "Tool failure" is shown. |
| Recursion limit in the worker | 6000 (endless recursion ends as a *Runtime error*) |
| Output | truncated at 20 000 characters |
| Results kept | the last 50 for the current revision |

## Known limitations

* Single user, one global state held in server memory: restarting the server (or Flask reloading)
  forgets the source; there are no accounts, saved collections or persistence.
* Timeout kills the whole worker; there is no separate Stop button (the timeout bounds every run).
* Values are shown as the interpreter's `repr` text (e.g. `D0Vint(arg1=42)`); closures show their
  environment and body.
* Type-check, Compile and Execute are placeholders by design (see ARCHITECTURE.md §6).
* Two browser tabs share one state; the second tab shows the first's state after a reload.
* The browser checks were automated in headless Chromium only; other browsers were not tested.
* Flask's development server is used (appropriate for local use only).

## Reflection (MVC)

MVC helped most where the assignment pushed hardest: state rules. Because the model owns the revision, the draft, the busy flag and the artifact, rules such as "no action while edits are unapplied" or "a new revision clears results and the generated-code artifact" live in one place and are tested without a browser or server. The same separation made the controller test easy: a FakeBackend could be dropped in to check dispatch, inject failures and prove that retry works, with no change to view code. Keeping the backend behind a protocol also meant the timeout, the worker process and the constructor reader never leaked into the rest of the app, and an import-graph test now guards that boundary.

Separation was hardest around editing. The textarea belongs to the browser, yet "unapplied edits block everything" is a model rule, so the draft has to be synchronised to the server, and the view must not overwrite what the user is typing; an editor epoch counter solved that but is extra machinery. The busy state was similar: the client disables buttons immediately, while the model remains the real authority. Deciding where button enablement logic lives (model availability versus view text) took several iterations. The browser test also exposed a stale-notice bug in the client, a reminder that the view half in JavaScript still needs its own tests.

The architecture makes a real compiler easy: implement Compile to return an artifact and Execute lights up with no view change. It would equally support a type checker, saving results per revision, or a second backend selectable at start-up.
