# LAMBDA3 JSON-RPC 2.0 service: RPC contract

API version: `1.0`. This document is the contract. The implementation and tests follow it, not the other way round.

The machine-readable envelope description is [`rpc.schema.json`](./rpc.schema.json) (JSON Schema, draft 2020-12).

Contents:

1. [Transport](#1-transport)
2. [JSON-RPC envelope, IDs, notifications, batches](#2-json-rpc-envelope-ids-notifications-batches)
3. [HTTP status vs RPC outcome](#3-http-status-vs-rpc-outcome)
4. [Methods](#4-methods)
5. [Error taxonomy](#5-error-taxonomy)
6. [Limits](#6-limits)
7. [Examples](#7-examples)
8. [Schema](#8-schema)
9. [Design decisions to review](#9-design-decisions-to-review)

## 1. Transport

There is exactly one endpoint. Operations are RPC methods in the payload, not URLs.

| Item | Contract |
| --- | --- |
| Endpoint | `POST /rpc` |
| Request media type | `Content-Type: application/json`. A `charset` parameter is accepted only if it is `utf-8`. |
| Request body | UTF-8 JSON: one request object, or a nonempty array of request objects (a batch). |
| Response media type | `application/json; charset=utf-8` whenever a body is sent. |
| Success of the transport | `200` with a JSON-RPC response (object or array), or `204` with an empty body. |
| Bind address | Local development and tests only. The default is `127.0.0.1:8000`. |

Transport failures happen before any JSON-RPC processing, so they use HTTP status codes and a body that is **not** a JSON-RPC response:

| Status | When |
| --- | --- |
| `404 Not Found` | Any path other than `/rpc`. |
| `405 Method Not Allowed` | `/rpc` called with anything other than `POST`. Sends `Allow: POST`. |
| `413 Content Too Large` | The raw request body exceeds 1 MiB (1,048,576 bytes). Checked before parsing. |
| `415 Unsupported Media Type` | `Content-Type` is missing, is not `application/json`, or has a non-UTF-8 charset. |

Everything that reaches the dispatcher gets `200` or `204`. This includes malformed JSON, invalid envelopes, unknown methods, bad params, LAMBDA errors, timeouts and internal errors. Section 3 gives the full rule.

Generated code is returned as text. The service never runs it, and it never uses Python `exec` or JavaScript evaluation.

## 2. JSON-RPC envelope, IDs, notifications, batches

### 2.1 Request object

```json
{ "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "6 * 7" }, "id": "answer" }
```

A request object is **valid** when all of these hold:

| Member | Rule | Violation |
| --- | --- | --- |
| (the item itself) | A JSON object. | `-32600`, reason `not_an_object` |
| `jsonrpc` | The string `"2.0"`. | `-32600`, reason `bad_jsonrpc_version` |
| `method` | A string. | `-32600`, reason `bad_method` |
| `id` | If present: a string, a number, or `null`. Booleans, objects and arrays are invalid. Integers are recommended. | `-32600`, reason `bad_id` |
| `params` | If present: an object or an array. A string, number, boolean or `null` is invalid. | `-32600`, reason `bad_params_type` |

Other members are ignored. Duplicate member names are not rejected (the last one wins, as in Python's JSON decoder).

Whether `params` has the shape a *method* needs is a separate check that happens after the method is found (section 4). An array `params` is a valid envelope but gets `-32602` from every method here, because all four methods need an object.

### 2.2 Calls and notifications

- A **call** is a valid request that has an `id` member. This includes `"id": null`. It always gets exactly one response.
- A **notification** is a valid request with **no `id` member at all**. `"id": null` is a call, not a notification.
- The server **executes** a notification and then discards the outcome. It sends nothing back for it, **not even an error**. An unknown method, bad params, a syntax error and a timeout in a notification are all silent for the client. The server logs them.
- Only a valid request can be a notification. A request that fails envelope validation always gets an Invalid Request response, even if it has no `id`.

### 2.3 Response object

Success:

```json
{ "jsonrpc": "2.0", "id": "answer", "result": { "type": "sint", "value": "42" } }
```

Failure:

```json
{ "jsonrpc": "2.0", "id": "answer", "error": { "code": -32011, "message": "LAMBDA type error", "data": { "kind": "type_error", "detail": "unbound variable 'x'" } } }
```

- Exactly one of `result` or `error` is present, never both.
- `error.code` is an integer. `error.message` is a short fixed string for each code (section 5). `error.data` is an object with the structured details. It is omitted where the table in section 5 says so.
- A response never contains a traceback, a Python exception class name, a filesystem path or a stack of any kind.

### 2.4 Request IDs

- The server returns the request's `id` unchanged (same type and value) in the response to a valid call.
- Responses to **invalid requests always have `"id": null`**, even if the broken request carried a usable-looking id. A request that failed validation cannot be trusted, and a fixed rule means a client never has to guess. This also covers the parse error and the whole-batch Invalid Request cases.
- Because of that, a client must not use `null` as an id for its own calls if it wants to tell its call results apart from Invalid Request errors. The service still accepts `"id": null` calls.
- The server does not check that ids are unique inside a batch. Duplicated ids make the client's matching ambiguous, which is the client's responsibility.

### 2.5 Batches

A batch is a JSON array of request objects.

| Case | Result |
| --- | --- |
| Empty array `[]` | One Invalid Request **object** (not an array), `-32600`, reason `empty_batch`, `id: null`. HTTP `200`. |
| More than 10 items | One Invalid Request object, `-32600`, reason `batch_too_large`, `id: null`. HTTP `200`. Nothing is executed. |
| An item that is not a valid request (for example `42`, `"x"`, `{}`, `[]`, wrong `jsonrpc`) | That item gets its own Invalid Request error with `id: null`, inside the response array. The other items are still processed. |
| An item that is a valid call | Gets its own response (a result or an error) with its own `id`. |
| An item that is a valid notification | Executed, and gets **no** entry in the response array. |

Processing rules:

- Items are independent. One item failing never affects another.
- Items are run one after another, in array order.
- The response array lists the responses in the order of the corresponding request items. **Clients must not rely on this order.** Match responses to calls by `id`.
- Several Invalid Request entries all have `id: null`, so they cannot be told apart by id. They appear in request order, but a client should not depend on that either.
- If the response array would be empty (every item was a valid notification), the server sends `204` with an empty body, never `[]`.

## 3. HTTP status vs RPC outcome

Two separate layers report success or failure:

- The **HTTP status** says whether the transport delivered a message to the JSON-RPC layer and whether a message comes back.
- The **JSON-RPC response** says whether the method call succeeded. A failed call is still a successful HTTP exchange.

### 3.1 Decision procedure

The server follows these steps in order. The first step that matches decides.

| # | Condition | HTTP | Body |
| --- | --- | --- | --- |
| 1 | Path is not `/rpc` | `404` | transport error |
| 2 | Method is not `POST` | `405` + `Allow: POST` | transport error |
| 3 | Body is larger than 1 MiB | `413` | transport error |
| 4 | `Content-Type` is not `application/json` (utf-8) | `415` | transport error |
| 5 | Body is not valid UTF-8 or not valid JSON | `200` | one Parse error object (`-32700`, `id: null`) |
| 6 | JSON value is an empty array | `200` | one Invalid Request object (`-32600`, `id: null`) |
| 7 | JSON value is an array of more than 10 items | `200` | one Invalid Request object (`-32600`, `id: null`) |
| 8 | JSON value is a nonempty array and at least one response is produced | `200` | array of responses |
| 9 | JSON value is a nonempty array and **no** response is produced (all items are valid notifications) | `204` | empty |
| 10 | JSON value is an object and it is a valid notification | `204` | empty |
| 11 | JSON value is an object (valid call, or invalid request) | `200` | one response object |
| 12 | JSON value is a string, number, boolean or `null` | `200` | one Invalid Request object (`-32600`, `id: null`) |

Steps 1 to 4 are the only transport failures. Steps 5 to 12 never use an HTTP error status.

`500`/`503` are reserved for a server that cannot produce any JSON-RPC response at all (for example, the process is shutting down). An internal error while handling a request is **not** that case: it is a `-32603` response with HTTP `200`.

### 3.2 Summary of the batch and notification cases

| Request | Items producing a response | HTTP | Body |
| --- | --- | --- | --- |
| Single call | 1 | `200` | object |
| Single valid notification | 0 | `204` | empty |
| Single invalid request | 1 (error) | `200` | object |
| Batch: 2 calls | 2 | `200` | array of 2 |
| Batch: 1 call + 1 notification | 1 | `200` | array of 1 |
| Batch: 1 call + 1 invalid item | 2 | `200` | array of 2 |
| Batch: 2 notifications | 0 | `204` | empty |
| Batch: 1 notification + 1 invalid item | 1 (error) | `200` | array of 1 |
| Batch: 1 notification that would fail (e.g. unknown method) | 0 | `204` | empty |
| Empty batch | 1 (error) | `200` | object |

The rule behind the table: **`204` if and only if the server produces zero JSON-RPC response objects. Otherwise `200`.** An invalid item always produces a response, so a batch that contains one can never be `204`.

## 4. Methods

Names are case-sensitive. All `params` for these methods must be a JSON object. Members that are not listed are rejected with `-32602` (`unexpected_param`), which catches typos such as `"sourc"`.

| Method | `params` | `result` |
| --- | --- | --- |
| `service.health` | `{}` (may be omitted) | `{ "status": "ok", "version": "1.0" }` |
| `lambda.typecheck` | `{ "source": string }` | `{ "type": string }` |
| `lambda.interpret` | `{ "source": string }` | `{ "type": string, "value": string }` |
| `lambda.compile` | `{ "source": string, "target": "python" \| "javascript" }` | `{ "target": string, "code": string }` |

### 4.1 Validation order

For a valid call, the server checks in this order and stops at the first failure:

1. Envelope (section 2.1): `-32600`.
2. Method name known: `-32601`.
3. `params` shape for that method: `-32602`.
4. Source size and blankness: `-32602`.
5. Execution: LAMBDA errors (`-32010`, `-32011`, `-32013`), timeout (`-32012`) or internal error (`-32603`).

An unknown method with bad params therefore reports `-32601`.

### 4.2 `params` validation

| Check | Failure |
| --- | --- |
| `params` is an array | `-32602`, reason `params_must_be_object` |
| `params` is omitted and the method needs `source` | `-32602`, reason `missing_param`, `param: "source"` |
| `source` missing | `-32602`, reason `missing_param`, `param: "source"` |
| `source` not a string (number, null, object, ...) | `-32602`, reason `wrong_type`, `param: "source"` |
| `source` empty or only whitespace (`source.strip() == ""`) | `-32602`, reason `blank`, `param: "source"` |
| `source` longer than 10,000 characters | `-32602`, reason `too_long`, `param: "source"`, `max_length: 10000` |
| `source` contains a lone UTF-16 surrogate escape (for example `"\ud800"`) | `-32602`, reason `invalid_unicode`, `param: "source"` |
| `target` missing on `lambda.compile` | `-32602`, reason `missing_param`, `param: "target"` |
| `target` not a string | `-32602`, reason `wrong_type`, `param: "target"` |
| `target` not `"python"` or `"javascript"` (case-sensitive) | `-32602`, reason `invalid_value`, `param: "target"`, `allowed: ["python", "javascript"]` |
| Any other member | `-32602`, reason `unexpected_param`, `param: <name>` |
| `service.health` with a nonempty `params` object | `-32602`, reason `unexpected_param` |

Source length is counted in Unicode characters of the decoded string, not bytes.

### 4.3 How each method uses LAMBDA3

All three source methods parse and type-check first. None of them interprets or compiles an expression that failed to type-check.

| Method | Steps (real signatures from `lambda3.py`) |
| --- | --- |
| `service.health` | None. Constant result. |
| `lambda.typecheck` | `expr, typ = d0exp_parse_and_typecheck(source)`; result `type = format_type(typ)`. |
| `lambda.interpret` | `expr, typ = d0exp_parse_and_typecheck(source)`; `val = d0exp_evaluate(expr)`; result `type = format_type(typ)`, `value = d0val_format(val)`. |
| `lambda.compile` | `expr, _ = d0exp_parse_and_typecheck(source)`; `code = d0exp_compile(expr)` for `python`, or `d0exp_compile_js(expr)` for `javascript`. The result `code` is the unmodified string. |

Notes that follow from the real implementation:

- `type` is whatever `format_type` returns: `sint`, `bool`, `unit`, `(sint, bool)`, `sint -> sint`, `List[sint]`, `Optn[sint]`, `A1sz[sint]`, and so on. An unconstrained type variable prints as `?t0` (for example `lam (x) => x` has type `?t0 -> ?t0`). That is valid output, not an error.
- `value` is always a **string** produced by `d0val_format`, so large integers keep full precision. Functions are `<lam>` or `<fix>`. Closure environments are never serialized.
- `print(...)` in a LAMBDA program writes to standard output when interpreted. The service captures that output and discards it. It is not part of the result.
- `lambda.compile` returns a self-contained program of about 5 KB, mostly a fixed runtime preamble followed by `_lambda_main`. It is a string. The service never executes it.
- The LAMBDA3 type-checker, not the service, rejects unbound variables (`-32011`, `unbound variable 'x'`).
- The `mylib/*.lam` standard library files are declaration files, not single expressions. The four methods take one expression and do not load them. Library programs are exercised through LAMBDA3 directly in the tests, not through these methods.

## 5. Error taxonomy

### 5.1 Table

`error.message` is the fixed string in the second column. Variable detail goes in `error.data`.

| Code | `message` | Meaning | HTTP | `data` |
| --- | --- | --- | --- | --- |
| `-32700` | `Parse error` | Body is not valid UTF-8 JSON. `id: null`. | 200 | `{ "reason": "invalid_json" \| "invalid_utf8" }` |
| `-32600` | `Invalid Request` | Envelope violates section 2.1, or the batch is empty or too large. `id: null`. | 200 | `{ "reason": <see 2.1 and 2.5> }` |
| `-32601` | `Method not found` | Valid call, method name not defined. | 200 | none |
| `-32602` | `Invalid params` | Section 4.2. | 200 | `{ "reason": ..., "param"?, "max_length"?, "allowed"? }` |
| `-32603` | `Internal error` | Unexpected server failure. | 200 | none |
| `-32010` | `LAMBDA syntax error` | `LambdaSyntaxError` raised while parsing. | 200 | `{ "kind": "syntax_error", "detail", "line", "column", "text" }` |
| `-32011` | `LAMBDA type error` | `TypeCheckError` raised while type-checking. | 200 | `{ "kind": "type_error", "detail" }` |
| `-32012` | `Execution timeout` | The 5 second deadline expired. | 200 | `{ "kind": "timeout", "limit_seconds": 5 }` |
| `-32013` | `LAMBDA runtime error` | A type-correct program failed while running. | 200 | `{ "kind": <see 5.3> }` |

`-32013` is an addition beyond the three application codes the assignment names. It sits in the allowed `-32000` to `-32099` range. The reason it exists: a program can pass the type-checker and still fail at run time (`1 / 0`, `list_head(list_nil())`). Folding those into `-32603` would blame the server for a client's program.

### 5.2 Where the application error data comes from

| Field | Source |
| --- | --- |
| `data.detail` (`-32010`) | `LambdaSyntaxError.msg`, for example `Expected an expression`. Not `str(exc)`, which appends `(<lambda>, line N)`. |
| `data.line`, `data.column` (`-32010`) | `LambdaSyntaxError.lineno` and `.offset`. Both are 1-based. The column counts within that line. |
| `data.text` (`-32010`) | `LambdaSyntaxError.text`: the offending line of the client's own source. |
| `data.detail` (`-32011`) | The `TypeCheckError` message, passed through unchanged. |

Two properties of LAMBDA3 shape these shapes:

- `TypeCheckError` carries only a message. It has **no line or column**, so `-32011` data has no position. The syntax error carries a position. The two `data` shapes differ for that reason, and `kind` tells the client which one it has.
- Type-checker messages are passed through as written. Some read oddly: `1 + true` yields `+: expected bool, got sint`, where the operands are in the opposite order from what a reader expects. The service does not rewrite them.

The fixed placeholder `"<lambda>"` that LAMBDA3 puts in `LambdaSyntaxError.filename` is never returned.

### 5.3 Runtime error kinds (`-32013`)

| `data.kind` | Raised by | Typical cause |
| --- | --- | --- |
| `division_by_zero` | `ZeroDivisionError` | `1 / 0`, `1 % 0` |
| `recursion_limit` | `RecursionError` | Recursion deeper than about 100 LAMBDA calls (for example `fact(150)`), or about 150 nested parentheses. This can occur while parsing or type-checking as well as evaluating. |
| `index_out_of_range` | `IndexError` | Array index or tuple projection out of range |
| `invalid_operation` | `ValueError` | `list_head(list_nil())`, `optn_get(optn_nil())`, `stcn_head` on an empty stream, a negative array size |
| `memory_limit` | `MemoryError` | The worker ran out of memory (for example an enormous array). Best effort: whether this fires depends on the memory ceiling the host enforces. |

`recursion_limit` is distinct from `-32012`. Hitting the recursion limit is a deterministic failure of that program, not a missed deadline.

### 5.4 What becomes `-32603`

Everything that is not in the table above, notably:

- Any unexpected exception in the adapter or dispatcher.
- A plain `TypeError` raised while *evaluating* a program that already passed type-checking. That would be a bug in LAMBDA3 or in the service. (`TypeCheckError` is a subclass of `TypeError`, so the adapter must catch `LambdaSyntaxError` and `TypeCheckError` explicitly rather than catching `TypeError`.)
- A failure of the worker process other than a timeout or a handled runtime error.

The `-32603` response has no `data`. The cause is logged on the server with its traceback. The log is never returned to the client.

### 5.5 Timeout

`-32012` means the deadline expired. **It does not prove the program fails to terminate**: it might finish given more time. The result of a timed-out request is discarded, and the work is stopped by terminating its worker.

## 6. Limits

| Limit | Value | Applies to | On violation |
| --- | --- | --- | --- |
| Request body | 1 MiB (1,048,576 bytes) | Whole HTTP body | HTTP `413` |
| `source` length | 10,000 characters | `source` of each call | `-32602` `too_long` |
| Batch size | 10 items | One batch array | `-32600` `batch_too_large` |
| Execution deadline | 5 seconds | Each source-method call (`lambda.typecheck`, `lambda.interpret`, `lambda.compile`), from the start of parsing to the end of the work | `-32012` |

### 6.1 Why these numbers

- **10,000 characters of source.** The largest example program in `LAMBDA3/mytest/` is 2,202 bytes (`eight_queens_stream.lam`) and the largest library file in `mylib/` is 5,577 bytes. 10,000 is more than four times the largest program, so no real example is close to the limit. It also keeps work per request small.
- **1 MiB body.** A batch of 10 calls with maximal sources, even if every character were written as a six-byte `\uXXXX` escape, is about 600,000 bytes plus envelope text. 1 MiB covers all legitimate requests with room to spare and still stops a client that sends megabytes before any parsing happens. The `source` limit is the one that clients are expected to meet, so it gets a precise RPC error. The body limit is a coarser transport guard.
- **Batch of 10.** There is no reason for more in a local development service, and the cap bounds the worst-case time of one HTTP request (see below).
- **5 seconds.** The interpreter is slow and recursive: measured on the reference machine, a doubly recursive Fibonacci takes about 0.27 s for `fib(20)` and about 4.8 s for `fib(26)`. Ordinary programs, including the factorial and eight-queens examples, finish in milliseconds. 5 seconds leaves a wide margin for legitimate work and still ends a runaway quickly. Because the interpreter's recursion depth is capped at about 100 calls, programs run long only through exponential recursion (or huge array construction), never through a deep stack.

The deadline covers parsing and type-checking as well as evaluation and compilation, so a pathological input cannot stall the service in any stage. Worst case for one HTTP request is 10 calls x 5 seconds = 50 seconds, since batch items run sequentially.

The deadline is enforced by running the work somewhere it can be forcibly stopped (a worker process that is terminated). The contract is only that expiry produces `-32012` and stops the work.

## 7. Examples

All request bodies are sent with `Content-Type: application/json` to `POST /rpc`. Each example shows the JSON body and the HTTP status of the reply. Responses are formatted for reading. The server may emit them compactly.

### 7.1 Health

Request:

```json
{ "jsonrpc": "2.0", "method": "service.health", "params": {}, "id": "health-1" }
```

Response, HTTP `200`:

```json
{ "jsonrpc": "2.0", "id": "health-1", "result": { "status": "ok", "version": "1.0" } }
```

### 7.2 Successful type-check

Request (the assignment's factorial program):

```json
{
  "jsonrpc": "2.0",
  "method": "lambda.typecheck",
  "params": { "source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end" },
  "id": 1
}
```

Response, HTTP `200`:

```json
{ "jsonrpc": "2.0", "id": 1, "result": { "type": "sint" } }
```

### 7.3 Successful interpretation

Request (same program):

```json
{
  "jsonrpc": "2.0",
  "method": "lambda.interpret",
  "params": { "source": "let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end" },
  "id": 2
}
```

Response, HTTP `200`:

```json
{ "jsonrpc": "2.0", "id": 2, "result": { "type": "sint", "value": "720" } }
```

A function and a tuple (request, then response):

```json
{ "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "let f : sint -> sint = lam (x: sint) => x in f end" }, "id": "fn" }
```

```json
{ "jsonrpc": "2.0", "id": "fn", "result": { "type": "sint -> sint", "value": "<lam>" } }
```

```json
{ "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "(1, true)" }, "id": "tup" }
```

```json
{ "jsonrpc": "2.0", "id": "tup", "result": { "type": "(sint, bool)", "value": "(1, true)" } }
```

### 7.4 Compilation

Request:

```json
{ "jsonrpc": "2.0", "method": "lambda.compile", "params": { "source": "1 + 2", "target": "python" }, "id": "c-py" }
```

Response, HTTP `200`. **The `code` string below is abbreviated for this document**: the real value is about 4.9 KB, starting with the runtime preamble (marked `…`) and ending exactly as shown. The service returns the generated text unchanged.

```json
{
  "jsonrpc": "2.0",
  "id": "c-py",
  "result": {
    "target": "python",
    "code": "…runtime preamble…\n\ndef _lambda_main():\n    _v1 = 1\n    _v2 = 2\n    _v3 = (_v1 + _v2)\n    return _v3\n\n_lambda_result = _lambda_main()\n"
  }
}
```

The JavaScript form differs only in `target` and `code`:

```json
{ "jsonrpc": "2.0", "method": "lambda.compile", "params": { "source": "1 + 2", "target": "javascript" }, "id": "c-js" }
```

```json
{
  "jsonrpc": "2.0",
  "id": "c-js",
  "result": {
    "target": "javascript",
    "code": "…runtime preamble…\n\nfunction _lambda_main() {\n  let _v1 = 1;\n  let _v2 = 2;\n  let _v3 = (_v1 + _v2);\n  return _v3;\n}\nconst _lambda_result = _lambda_main();\n"
  }
}
```

### 7.5 Syntax error (`-32010`)

Request:

```json
{ "jsonrpc": "2.0", "method": "lambda.typecheck", "params": { "source": "if then" }, "id": "syntax" }
```

Response, HTTP `200`:

```json
{
  "jsonrpc": "2.0",
  "id": "syntax",
  "error": {
    "code": -32010,
    "message": "LAMBDA syntax error",
    "data": { "kind": "syntax_error", "detail": "Expected an expression", "line": 1, "column": 4, "text": "if then" }
  }
}
```

### 7.6 Type error (`-32011`)

An unbound variable, rejected by the LAMBDA3 type-checker:

```json
{ "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "x + 1" }, "id": "unbound" }
```

Response, HTTP `200`:

```json
{
  "jsonrpc": "2.0",
  "id": "unbound",
  "error": {
    "code": -32011,
    "message": "LAMBDA type error",
    "data": { "kind": "type_error", "detail": "unbound variable 'x'" }
  }
}
```

Nothing was interpreted. A type error has no line or column.

### 7.7 Runtime error (`-32013`) and timeout (`-32012`)

A type-correct program that divides by zero:

```json
{ "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "1 / 0" }, "id": "div" }
```

```json
{
  "jsonrpc": "2.0",
  "id": "div",
  "error": { "code": -32013, "message": "LAMBDA runtime error", "data": { "kind": "division_by_zero" } }
}
```

A program that runs past the deadline (doubly recursive Fibonacci of 35):

```json
{
  "jsonrpc": "2.0",
  "method": "lambda.interpret",
  "params": { "source": "let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(35) end" },
  "id": "slow"
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "slow",
  "error": { "code": -32012, "message": "Execution timeout", "data": { "kind": "timeout", "limit_seconds": 5 } }
}
```

### 7.8 Envelope-level errors

Malformed JSON, HTTP `200`. Request body (raw text, not valid JSON): `{"jsonrpc":`

```json
{ "jsonrpc": "2.0", "id": null, "error": { "code": -32700, "message": "Parse error", "data": { "reason": "invalid_json" } } }
```

Wrong version. Request `{"jsonrpc": "1.0", "method": "service.health", "id": 1}`, HTTP `200`. Note `id` is `null` even though the request had `1`:

```json
{ "jsonrpc": "2.0", "id": null, "error": { "code": -32600, "message": "Invalid Request", "data": { "reason": "bad_jsonrpc_version" } } }
```

Unknown method. Request `{"jsonrpc": "2.0", "method": "does.not.exist", "id": "unknown"}`, HTTP `200`:

```json
{ "jsonrpc": "2.0", "id": "unknown", "error": { "code": -32601, "message": "Method not found" } }
```

Blank source. Request `{"jsonrpc": "2.0", "method": "lambda.interpret", "params": {"source": "   "}, "id": "blank"}`, HTTP `200`:

```json
{ "jsonrpc": "2.0", "id": "blank", "error": { "code": -32602, "message": "Invalid params", "data": { "reason": "blank", "param": "source" } } }
```

Unsupported media type: a request sent as `text/plain` receives HTTP `415` and no JSON-RPC response.

### 7.9 Mixed batch: calls, a notification and invalid items

Request. In order: a call; a notification (no `id`); a call that fails type-checking; a notification that would fail (unknown method); and an item that is not an object.

```json
[
  { "jsonrpc": "2.0", "method": "lambda.interpret", "params": { "source": "6 * 7" }, "id": "answer" },
  { "jsonrpc": "2.0", "method": "service.health", "params": {} },
  { "jsonrpc": "2.0", "method": "lambda.typecheck", "params": { "source": "x + 1" }, "id": 7 },
  { "jsonrpc": "2.0", "method": "does.not.exist" },
  42
]
```

Response, HTTP `200`. Three entries: the two calls and the invalid item. The two notifications are executed but produce nothing, even though one of them failed:

```json
[
  { "jsonrpc": "2.0", "id": "answer", "result": { "type": "sint", "value": "42" } },
  { "jsonrpc": "2.0", "id": 7, "error": { "code": -32011, "message": "LAMBDA type error", "data": { "kind": "type_error", "detail": "unbound variable 'x'" } } },
  { "jsonrpc": "2.0", "id": null, "error": { "code": -32600, "message": "Invalid Request", "data": { "reason": "not_an_object" } } }
]
```

A client matches `"answer"` and `7` by `id`. The `null` entry belongs to no call of the client's.

### 7.10 Notification-only batch

Request. Both items are valid notifications. The second one would fail if it were a call:

```json
[
  { "jsonrpc": "2.0", "method": "service.health", "params": {} },
  { "jsonrpc": "2.0", "method": "lambda.typecheck", "params": { "source": "x + 1" } }
]
```

Response: HTTP `204 No Content`, empty body. No `Content-Type`, no JSON, and not `[]`.

### 7.11 Single notification and empty batch

A single valid notification, `{"jsonrpc": "2.0", "method": "service.health", "params": {}}`, gets HTTP `204` with an empty body.

The empty batch `[]` gets HTTP `200` and one object, not an array:

```json
{ "jsonrpc": "2.0", "id": null, "error": { "code": -32600, "message": "Invalid Request", "data": { "reason": "empty_batch" } } }
```

## 8. Schema

[`rpc.schema.json`](./rpc.schema.json) is a JSON Schema (draft 2020-12). Entry points:

| Definition | Describes |
| --- | --- |
| `#/$defs/requestBody` | What a client POSTs: one request, or a batch array of 1 to 10 items. |
| `#/$defs/responseBody` | What the server returns with HTTP `200`: one response, or a nonempty array of responses. |
| `#/$defs/methodCall` | Per-method `params` constraints for the four defined methods. |
| `#/$defs/errorObject` | The error object, with the allowed codes and the `data` shape for each code. |

An HTTP `204` reply has no body and so no schema. Batch items are validated one at a time by the server, so `batchRequest` constrains only the array itself, and an invalid item is answered with `-32600` rather than making the whole batch invalid.

## 9. Design decisions to review

These are choices the assignment text leaves open or where the obvious reading is easy to get wrong:

1. **Invalid Request always has `id: null`**, even if the request carried a usable id. The provided contract test (`TEST/test_rpc_api.py`, `test_invalid_request_and_empty_batch`) requires `id: null` for `{"jsonrpc": "1.0", ..., "id": 1}`.
2. **Valid notifications never get a response, not even an error.** This follows JSON-RPC 2.0 section 4.1. The consequence is that a batch of only failing notifications still returns `204`.
3. **`"id": null` is a call.** A notification is the absence of the `id` member.
4. **`params` typing.** A non-structured `params` (string, number, boolean, `null`) is an envelope error (`-32600`), per JSON-RPC section 4.2. An array `params` is a valid envelope that these methods reject with `-32602`.
5. **Strict `params`.** Unknown members in `params` are rejected (`-32602`, `unexpected_param`).
6. **`-32013` runtime error** is an extra application code; `RecursionError` maps to it (kind `recursion_limit`), not to `-32012` and not to `-32603`.
7. **The deadline covers parse and type-check as well as evaluation.** Parsing and type-checking can themselves overflow the stack on nested input.
8. **Batch size cap of 10**, and one Invalid Request object (not an array) when it is exceeded.
9. **Standard library files are not reachable through the four methods.** They are declaration files, and the methods take a single expression.
