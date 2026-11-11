# Testing

## Architecture

```
  HTTP client (curl, TEST/, Flask test client)
        │  POST /rpc, application/json
        ▼
┌────────────────────────────┐
│ app.py: HTTP transport     │  404 / 405 / 413 / 415; raw body in; 200 or 204 out
└─────────────┬──────────────┘
              │ raw bytes
              ▼
┌────────────────────────────┐
│ jsonrpc.py: dispatcher     │  parse JSON, validate envelope, batches, notifications,
│                            │  ids, route method name → handler, build responses
└─────────────┬──────────────┘
              │ params (dict)
              ▼
┌────────────────────────────┐
│ methods.py: RPC methods    │  validate params, map outcomes to -32010/11/12/13/-32603
└─────────────┬──────────────┘
              │ backend(op, source, target)   ◄── test doubles plug in here
              ▼
┌────────────────────────────┐
│ runner.py: deadline        │  spawn worker process, kill it after 5 s
└─────────────┬──────────────┘
              │ (worker process)
              ▼
┌────────────────────────────┐
│ lambda_service.py: adapter │  only importer of lambda3; returns plain data
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ LAMBDA3/lambda3.py         │  d0exp_parse_and_typecheck, d0exp_evaluate,
│ (provided, unmodified)     │  format_type, d0val_format, d0exp_compile, d0exp_compile_js
└────────────────────────────┘
```

Only `lambda_service.py` imports `lambda3`. `jsonrpc.py` knows nothing about LAMBDA3, and `methods.py` knows nothing about envelopes beyond raising `RpcError`. The seam for test doubles is the `backend` argument of `create_app(backend=...)`. The default backend is the real `runner.run_with_deadline`.

## How to run

From `assigns/07/`:

```bash
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v
```

```bash
python3 -m unittest discover -s TEST -v
```

The second command needs the server running (`cd MySolution && .venv/bin/python -m rpc_service`).

## Observed results

Recorded on 2026-11-10 with Python 3.15.2, Flask 3.1.3, on macOS 26.5.1 (arm64):

| Suite | Tests | Result | Time |
| --- | --- | --- | --- |
| `MySolution/tests/test_rpc_http.py` (Flask test client) | 47 | **all passed** | 3.1 s |
| `TEST/test_rpc_api.py` (provided, against the live server) | 15 | **all passed** | 0.5 s |

Manual checks against the live server, with outputs shown in README.md:

- Every curl example in README.md was run against the server and returned the output shown there.
- A real `fib(35)` call returned `-32012` after 5.05 s.
- After the run, no worker process was left alive (no `multiprocessing.spawn` process in `ps`).

## Requirement → test mapping

"Real" means the test runs real LAMBDA3 in a real worker process through the Flask test client. "Double" means the backend is replaced by a test double (`Recorder` or `flaky` in the test file). Doubles are used only for failure injection and dispatch-boundary checks, never for a success path.

| # | Required behavior | Test(s) in `test_rpc_http.py` | Backend | Result |
| --- | --- | --- | --- | --- |
| 1 | `service.health` returns status and API version, preserves id | `test_health_returns_version_and_preserves_id` (ids `"health-1"`, `7`, `null`), `test_health_params_may_be_omitted`, `test_id_types_are_preserved` (string, empty string, 0, negative, float, 10^30, null) | real | pass |
| 2 | Type-checking valid programs gives the formatted type | `test_typecheck_valid_programs` (`1 + 2`, factorial, `(1, true)`, `lam (x: sint) => x`, `true`, a list) | real | pass |
| 3 | Interpretation: arithmetic, factorial, a tuple, a collection | `test_arithmetic` (`42`), `test_factorial` (`720`), `test_tuple` (`(1, true)`), `test_collections` (List, A1sz, Optn); also `test_print_output_is_discarded`, `test_large_integer_keeps_precision` (90!) | real | pass |
| 4 | Python and JavaScript compilation: nonempty code, correct `target` | `test_python_and_javascript_return_unchanged_lambda3_output` (code equals LAMBDA3's own `d0exp_compile` / `d0exp_compile_js` output byte for byte), `test_compile_still_type_checks_first` | real | pass |
| 5 | Syntax and type errors have distinct documented codes | `test_syntax_and_type_errors_have_distinct_codes_and_data` (-32010 with line/column/text vs -32011), `test_multiline_syntax_error_position`, `test_no_traceback_or_path_in_any_lambda_error` | real | pass |
| 5+ | Runtime errors (`-32013`, our added code) | `test_runtime_errors_are_their_own_code` (division by zero, empty list head, array index), `test_deep_recursion_is_recursion_limit_not_internal`, `test_deeply_nested_parentheses_in_typecheck` | real | pass |
| 6 | Malformed JSON | `test_malformed_json_is_parse_error_with_http_200` (truncated, empty, `not json`, NaN, 100,000 nested brackets, invalid UTF-8) | real | pass |
| 6 | Invalid envelopes | `test_invalid_envelopes_get_invalid_request_with_null_id` (13 cases: version, method, id, params types, non-objects), `test_infinite_float_id_is_invalid` | real | pass |
| 6 | Unknown method | `test_unknown_method_wins_over_bad_params` (including case sensitivity) | real | pass |
| 6 | Absent or wrongly typed params, blank source | `test_param_validation` (16 cases: blank, empty, wrong types, missing, array params, unexpected members, bad or missing target, lone surrogate) | real | pass |
| 6 | Oversized source | `test_source_size_limit_is_exact` (10,000 characters accepted, 10,001 rejected with `too_long`), `test_oversized_body_is_413` | real | pass |
| 6 | Transport errors | `test_wrong_media_type_is_415_not_a_rpc_response`, `test_utf8_charset_parameter_is_accepted`, `test_other_verbs_and_paths` (405, 404) | real | pass |
| 7 | Function result formatted without closure internals | `test_function_value_does_not_leak_closure` (`<lam>` and `<fix>`) | real | pass |
| 8 | Injected backend failure: `-32603`, id preserved, no traceback | `test_unexpected_backend_failure_is_32603_without_details` (exception text containing a path and "Traceback" is logged but absent from the response), `test_worker_internal_failure_is_32603_and_logged`, `test_notification_that_crashes_is_silent_and_logged`, `test_one_failing_batch_item_does_not_affect_others` | double | pass |
| 8 | Injected timeout: `-32012`, id preserved | `test_timeout_is_32012_and_preserves_id` | double | pass |
| 8 | Real deadline kills runaway work | `test_runaway_computation_is_killed_and_reported_as_timeout` (`fib(35)` with a 0.5 s deadline: `-32012` in under 5 s, no leftover process), `test_service_still_works_after_a_timeout` | real (short deadline) | pass |
| 9 | LAMBDA3 type-checking rejects an unbound variable | `test_unbound_variable_is_rejected_by_lambda3_typechecker` (`x + 1` gives `-32011`, `unbound variable 'x'`) | real | pass |
| 10 | Batch responses preserve ids, omit notifications | `test_responses_match_by_id_and_omit_notifications` (responses matched through an id map, not array position) | real | pass |
| 10 | Invalid batch members get `id: null` Invalid Request | `test_invalid_members_get_null_id_errors_and_others_still_run` | real | pass |
| 10 | Notification-only batch: 204, empty body | `test_notification_only_batch_is_204_with_empty_body` (also no `Content-Type`), `test_failing_notifications_stay_silent` | real | pass |
| 10 | Empty batch: one Invalid Request object | `test_empty_batch_is_one_invalid_request_object` | real | pass |
| 10 | Single notification: 204, no body | `test_single_notification_is_204`, `test_null_id_is_a_call_not_a_notification` | real | pass |
| 10 | Batch size cap | `test_oversized_batch_runs_nothing` (11 rejected, 10 accepted) | real | pass |
| – | Dispatch boundary | `test_invalid_params_never_reach_the_backend`, `test_valid_notification_is_executed_but_silent` | double | pass |

## Provided contract tests (`TEST/test_rpc_api.py`)

All 15 passed against the live server:

| Test | Result |
| --- | --- |
| `test_health` | ok |
| `test_typecheck_arithmetic` | ok |
| `test_interpret_arithmetic` | ok |
| `test_interpret_tuple` | ok |
| `test_interpret_list` | ok |
| `test_interpret_function_formats_closure` | ok |
| `test_compile_python_and_javascript` | ok |
| `test_language_syntax_and_type_errors_are_distinct` | ok |
| `test_invalid_params_and_unknown_method` | ok |
| `test_malformed_json_returns_parse_error` | ok |
| `test_batch_matches_by_id_and_omits_notification` | ok |
| `test_notification_only_batch_has_no_response` | ok |
| `test_notification_has_no_response` | ok |
| `test_invalid_request_and_empty_batch` | ok |
| `test_malformed_batch_member_gets_null_id_error` | ok |

## Not covered by automated tests

- **The full 5 s deadline.** It was only checked manually: a real `fib(35)` returned after 5.05 s. The automated test uses a 0.5 s deadline to keep the suite fast.
- **The memory ceiling (`memory_limit`).** It is set only on Linux and was not exercised on macOS.
- **The JSON Schema.** `rpc.schema.json` was checked to be valid JSON, but the examples were not validated against it (no `jsonschema` package installed).
- **Running generated code.** The service never runs it, so its behavior is out of scope here. LAMBDA3's own `mytest/check_examples.py` covers that.
