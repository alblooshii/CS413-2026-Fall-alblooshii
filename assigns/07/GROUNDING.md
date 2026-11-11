# Assign07 grounding: the real LAMBDA3 interface

Source: `assigns/07/LAMBDA3/lambda3.py` (1904 lines), Python 3.15.2 locally.
Everything marked **(probed)** was run against the module, not just read.
No RPC code is designed or written here.

## 1. Function signatures and behavior

| Function | Signature (line) | Behavior |
| --- | --- | --- |
| `d0exp_parse_and_typecheck` | `(source: str) -> tuple[d0exp, simple_type]` (1306) | `d0exp_parse(source)` then `d0exp_typecheck(expr)`. Returns `(AST, type)`. Raises `LambdaSyntaxError` or `TypeCheckError`. Nothing else is wrapped. |
| `d0exp_evaluate` | `(dexp, denv=ENVnil()) -> d0val` (403) | Recursive big-step interpreter. Returns a `D0V*` object. No step budget, no deadline. Raises plain Python exceptions (see section 3). |
| `format_type` | `(typ) -> str` (1048) | `sint`, `bool`, `void`, `unit` (empty tuple), `(sint, bool)`, `sint -> sint`, `List[T]`, `Optn[T]`, `A1sz[T]`, `Lazy[T]`, `Stcn[T]`. Unresolved metas print as `?t0`. Raises `TypeError` on an unknown type object. |
| `d0val_format` | `(dval) -> str` (288) | `7`, `true`, `(1, true)`, `(1,)`, `[1, 2]`, `<lazy>`, `stcn_cons(h, <lazy>)`, `optn_cons(x)`, `optn_nil()`, `<lam>`, `<fix>`. Never exposes the closure environment. Raises `TypeError` for an unsupported value. |
| `d0exp_compile` | `(dexp) -> str` (1865) | Returns a complete Python program: a runtime preamble, `_lambda_main()`, and a final `_lambda_result = _lambda_main()`. About 4.9 KB even for `1+2` (probed). Does not execute anything. |
| `d0exp_compile_js` | `(dexp) -> str` (1885) | Same shape for JavaScript: a runtime preamble, `_lambda_main()`, and `const _lambda_result = ...`. About 5 KB (probed). |

Other facts that affect the design:

- `d0exp_compile` and `d0exp_compile_js` take the **AST**, not source text. The service must call `d0exp_parse_and_typecheck` first and pass in the returned expression.
- Compiling an expression that was never type-checked can raise `ValueError("unbound variable during compilation: x")` (probed). The type-check step prevents this.
- `d0exp_evaluate` of an unbound variable does **not** raise. It silently returns the sentinel `D0V000()`, and `d0val_format` would then raise `TypeError` (probed). The type-check step prevents this too.
- `print(e)` in LAMBDA writes to the process's real `sys.stdout` during interpretation (probed: `print(5)` gives type `unit`, value `()`, and `5\n` on stdout). The server needs to capture or discard that output, or it will leak into server logs and mix with other requests.
- Arrays (`A1sz`) are mutable Python lists inside the AST values. Evaluating the same AST twice gives fresh arrays because construction happens at evaluation time (probed), so no cross-request state leaks as long as the AST is not cached.
- `D0Vlazy` and `D0Vstcn` have mutable state. This is relevant for Assign08, not for the four required methods.

## 2. How the two error types are raised and what they carry

### `LambdaSyntaxError(SyntaxError)` (line 671)

Raised only by the tokenizer and parser, through `_syntax_error(source, offset, message)` (line 697). It is built as:

```python
LambdaSyntaxError(message, ('<lambda>', line, column, source_line_text))
```

Because it subclasses `SyntaxError`, these attributes are populated (probed):

| Attribute | Example for `"1 $ 2"` | Notes |
| --- | --- | --- |
| `.msg` | `"Unexpected character '$'"` | Clean message. Use this. |
| `.lineno` | `1` | One-based. |
| `.offset` | `3` | One-based column. |
| `.text` | `"1 $ 2"` | The offending source line only. |
| `.filename` | `"<lambda>"` | A fixed placeholder, not a filesystem path. |
| `.args` | `(msg, ('<lambda>', 1, 3, '1 $ 2'))` | |
| `str(exc)` | `"Unexpected character '$' (<lambda>, line 1)"` | Do not use this for `error.message`. It appends `(<lambda>, line N)`. |

Message shapes seen: `Unexpected character 'X'`, `Expected 'TOKEN', found 'Y'`, `Expected 'TOKEN', found end of input`, `Expected an expression`, `Duplicate type parameter`.

Column for a multi-line source is relative to its own line (probed: `let x = 1\nin x +\nend` gives line 3, column 1, text `end`). The empty string is a syntax error ("Expected an expression", line 1, column 1).

### `TypeCheckError(TypeError)` (line 966)

Raised only inside `d0exp_typecheck` and `_TypeSolver.unify`. It carries **only a message** (`.args == (message,)`). There is no line, column, or source span (probed). `str(exc)` is the clean message.

Messages seen:

- `unbound variable 'x'`
- `+: expected bool, got sint` (for `1 + true`; see mismatch 5)
- `if condition: expected bool, got sint`
- `lambda: expected function type, got ...`
- `unbound type variable 'T'; declare it ...`
- Plus infinite type, polymorphism, tuple projection, and unknown-operator messages.

### Not wrapped, so these arrive as raw Python exceptions

Probed:

| Situation | Exception | Raised from |
| --- | --- | --- |
| `1 / 0` or `1 % 0` | `ZeroDivisionError` | `d0exp_evaluate` |
| `fact(150)`, or any recursion deeper than about 100 frames of LAMBDA calls | `RecursionError` | `d0exp_evaluate` |
| 150 or more nested parentheses | `RecursionError` | the **parser** (and the type-checker) |
| `list_head(list_nil())`, `optn_get(optn_nil())` | `ValueError` | `d0exp_evaluate` |
| Array index out of range, tuple index out of range | `IndexError` | `d0exp_evaluate` |
| Non-`str` input to the parser | `TypeError` (not `TypeCheckError`) | the parser |

`TypeCheckError` subclasses `TypeError`. Evaluation also raises plain `TypeError`. A broad `except TypeError` would therefore misclassify runtime failures as type-check errors. Catch the two specific classes.

## 3. Mismatches between the spec and the code

Ordered by how much they matter for the design.

1. **Runtime errors have no code in the spec.** The spec defines `-32010` (syntax), `-32011` (type), and `-32012` (timeout). The probes show that type-correct programs still fail at runtime: `1 / 0`, `list_head(list_nil())`, index out of range, and `RecursionError`. The spec says only "unexpected failures produce `-32603`." Decision for you: should `1 / 0` be a `-32603` internal error, which is what the spec literally implies, or a new application code in `-32000` to `-32099`, which is friendlier? The spec does not forbid the second.

2. **Recursion depth is tiny (about 100 LAMBDA call frames).** Python's recursion limit is 1000, and each LAMBDA call uses several Python frames. `fact(100)` works and `fact(150)` raises `RecursionError`. The assignment's own example is `fact(6)`, which is fine. This means deep recursion fails fast with `RecursionError`, not with a timeout. The spec only mentions a timeout, so `RecursionError` needs an explicit mapping. It is a deterministic resource-limit failure, not an internal bug. If the interpreter runs in a worker process or thread, the recursion limit is per-thread and can differ.

3. **Parser and type-checker can also hit `RecursionError`.** About 150 nested parentheses is enough (probed). The spec's "syntax error vs type error vs internal error" split does not cover this. A maximum source size alone does not prevent it, since 150 parentheses is tiny. Needs a mapping too.

4. **The spec says "standard library modules in `LAMBDA3/mylib/` ... available for demonstrations and tests." They are not Python modules.** They are `.lam` declaration files (`list.lam`, `optn.lam`, `a1sz.lam`, `strm.lam`). They are loaded with `d0cls_parse` + `d0cls_typecheck` and used as `D0Elets(declarations, d0exp_parse(source))` (see `mylib/TEST/test_list_library.py`). **`d0exp_parse_and_typecheck(source)` cannot see them.** The six functions the spec lists do not include `d0cls_parse`, `d0cls_typecheck`, or `D0Elets`. To make the library available, the service layer would need to use those additional functions, and also `d0exp_typecheck` / `d0exp_compile` on the combined AST. Whether and how to expose the library is a real design decision (always preloaded, opt-in param, or not exposed), and it is not specified. The simplest reading is that the required four methods do not need the library, and "available" means it works when someone chooses to use it.

5. **The type-error message text can read backwards.** For `1 + true` the message is `+: expected bool, got sint`. The operands are the other way round: `+` expects `sint` and received `bool`. The unifier's left and right sides are not labeled consistently. This affects "useful client-facing diagnostics." Do not rewrite the text. Pass it through as `data.message` and note the quirk in `RPC.md`.

6. **`TypeCheckError` has no position, though `LambdaSyntaxError` does.** The spec asks for "useful client-facing diagnostics" for both. Syntax errors can carry `line`, `column`, and `text`. Type errors can only carry `message`. `data` shapes for the two codes will differ, and the docs should say so.

7. **Closure formatting, as the spec expects.** `d0val_format` returns `<lam>` / `<fix>` (probed). It matches the spec, no mismatch.

8. **Printing.** `print(...)` inside LAMBDA source writes to the real stdout. The spec does not mention it. `lambda.interpret` returns only `type` and `value`. Capture or discard the printed text, and decide whether to document it as dropped.

9. **Interpreted vs compiled output are not identical in every case.** The compiled Python and JS programs are self-contained and returned as text. They are never executed by the service, so this only matters for documentation. Compile output for a function is a valid program that produces a function.

10. **Large integers.** `value` is a decimal string, so JSON precision is not an issue. Python's default limit of 4300 digits for `int` to `str` conversion could raise `ValueError` inside `d0val_format`. In practice `RecursionError` fires first for factorial-style programs, but a loop-free doubling program could reach it. Low priority.

11. **Spec says `params` is an object, and `source` must be nonempty.** The code accepts any `str`, including whitespace-only strings, and `""` fails as a syntax error ("Expected an expression"). The "blank source" check (`-32602`) is the service's job, not LAMBDA3's. A whitespace-only source would otherwise surface as `-32010`. The spec's test list says blank source gets handled as specified, so `.strip() == ""` should be rejected as `-32602`. Confirm that reading.

12. **`SYNTAX.md` is referenced in a code comment (line 666) but does not exist** in `LAMBDA3/`. Concrete syntax has to be inferred from `mytest/*.lam` and the parser. Note that `lam x => x` is a syntax error (parameters need parentheses: `lam (x) => x` or `lam (x: sint) => x`).

13. **Polymorphic or unresolved types print with metas.** `lam (x) => x` type-checks to `?t0 -> ?t0` (probed). `format_type` will return that. It is a valid string, but clients may find it odd.

14. **Environment version.** Local Python is 3.15.2. The spec says 3.12 or later. `lambda3.py` uses the `type X = ...` statement (3.12+), so 3.12 is the real floor.

## 4. Practical consequences for the design (not code)

- The service adapter needs exactly this exception map. Catch `LambdaSyntaxError` for `-32010` (data: `line`, `column`, `text`, `message`). Catch `TypeCheckError` for `-32011` (data: `message`). Treat timeout as `-32012`. Everything else, including `RecursionError`, `ZeroDivisionError`, `ValueError`, and `IndexError`, goes to `-32603` unless you decide to add a runtime-error code (mismatch 1).
- Order of `except` clauses matters because `LambdaSyntaxError` and `TypeCheckError` have broad base classes.
- `RecursionError` can occur in the parse and type-check step as well as in evaluation. A worker process (or thread with a controlled stack size) around **all** of parse, check, and evaluate is safer than around evaluation only. Compilation does not appear to be unbounded, but it can be exercised on deeply nested input too.
- A hard deadline needs a **process**, not a thread, because Python cannot kill a thread. Captured stdout must be handled inside that worker.

## 5. Decisions

**Decided (user): runtime failures get their own application code.**

- `-32013` "LAMBDA runtime error" covers `ZeroDivisionError`, `ValueError` and `IndexError` from `d0exp_evaluate`, and `RecursionError` from any stage. It is not `-32603`, and not `-32012`, because the timeout code should mean only a missed deadline.
- `data` carries a short `kind` (for example `"division_by_zero"`, `"recursion_limit"`, `"empty_list"`) plus a fixed client-safe `message`. It never carries `str(exc)` or a traceback.
- Anything outside that list still maps to `-32603`.
- `-32013` is outside the assignment's required codes (`-32010` to `-32012`). It must be documented in `RPC.md`.
- A plain `TypeError` raised during evaluation after a successful type-check is a bug, so it stays `-32603`.

**Still open:**

1. Should the `mylib` `.lam` files be exposed at all (always loaded, opt-in, or only used in tests)?
2. Reject whitespace-only `source` as `-32602`, as I read the spec?
