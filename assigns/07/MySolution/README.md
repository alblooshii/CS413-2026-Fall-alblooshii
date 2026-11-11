# LAMBDA3 JSON-RPC service (Assign07)

A JSON-RPC 2.0 service that exposes the LAMBDA3 type-checker, interpreter and Python/JavaScript compilers over one HTTP endpoint, `POST /rpc`. The full contract (envelopes, error codes, limits, batches) is in [RPC.md](./RPC.md). The envelope JSON Schema is [rpc.schema.json](./rpc.schema.json). Test mapping and results are in [TESTING.md](./TESTING.md).

**Generated code is returned, never executed.** `lambda.compile` returns the text produced by LAMBDA3's `d0exp_compile` / `d0exp_compile_js` unchanged. The service does not run it, and no part of the service uses Python `exec` or JavaScript evaluation. Only `lambda.interpret` runs a program, and it does so with LAMBDA3's own interpreter inside a worker process that is killed after 5 seconds.

## Versions used

| Component | Version |
| --- | --- |
| Python | 3.15.2 (3.12 or later required: `lambda3.py` uses the `type` statement) |
| Flask | 3.1.3 (pinned in `requirements.txt`) |
| Werkzeug | 3.1.9 (installed by Flask) |
| Tested on | macOS 26.5.1, arm64 |

Tests use the standard library's `unittest` and Flask's built-in test client. Nothing else is installed.

## Directory layout

The service expects the assignment layout, with `LAMBDA3/` next to `MySolution/`:

```
assigns/07/
├── LAMBDA3/              provided: lambda3.py, basics0.py, mylib/, mytest/
├── TEST/                 provided: black-box contract tests against a running server
└── MySolution/
    ├── RPC.md, rpc.schema.json
    ├── README.md, TESTING.md, AI-TRANSCRIPT.md
    ├── requirements.txt
    ├── rpc_service/
    │   ├── __main__.py       entry point: python -m rpc_service
    │   ├── app.py            HTTP transport (Flask)
    │   ├── jsonrpc.py        envelope, batches, notifications, dispatch
    │   ├── methods.py        the four methods: params validation, error mapping
    │   ├── runner.py         worker process with a hard 5 s deadline
    │   └── lambda_service.py adapter: the only module that imports lambda3
    └── tests/test_rpc_http.py
```

To load LAMBDA3 from somewhere else, set `LAMBDA3_DIR` to the directory that contains `lambda3.py`.

## Setup

From `assigns/07/MySolution/`:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

`.venv/` is git-ignored and is not part of the submission.

## Run the tests

From `assigns/07/`.

The service's own HTTP tests (Flask test client, no server needed):

```bash
MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v
```

The provided black-box contract tests, which need the server running (see below):

```bash
python3 -m unittest discover -s TEST -v
```

Observed results are recorded in [TESTING.md](./TESTING.md): 47/47 and 15/15 passing.

## Start the server

From `assigns/07/MySolution/`:

```bash
.venv/bin/python -m rpc_service
```

It listens on `127.0.0.1` only, port 8000 by default. Set `PORT` to change it, for example `PORT=9000 .venv/bin/python -m rpc_service`. It is the Flask development server, meant for local development and tests, not public deployment. Stop it with Ctrl-C.

**Endpoint URL: `http://127.0.0.1:8000/rpc`.** Only `POST` with `Content-Type: application/json` is accepted.

## Methods

| Method | `params` | `result` |
| --- | --- | --- |
| `service.health` | `{}` or omitted | `{"status": "ok", "version": "1.0"}` |
| `lambda.typecheck` | `{"source": "..."}` | `{"type": "..."}` |
| `lambda.interpret` | `{"source": "..."}` | `{"type": "...", "value": "..."}` |
| `lambda.compile` | `{"source": "...", "target": "python" \| "javascript"}` | `{"target": "...", "code": "..."}` |

`source` must be a nonblank string of at most 10,000 characters. Every source method parses and type-checks before doing anything else.

## curl examples

All outputs below were captured from the running server (HTTP headers trimmed to the status and content type). Each command is one line, so it can be copied as is.

### `service.health`

```bash
curl -s -i -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"service.health","params":{},"id":"health-1"}'
```

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

{"jsonrpc": "2.0", "id": "health-1", "result": {"status": "ok", "version": "1.0"}}
```

### `lambda.typecheck`: factorial

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"},"id":1}'
```

```json
{"jsonrpc": "2.0", "id": 1, "result": {"type": "sint"}}
```

### `lambda.interpret`: factorial

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"let fact : sint -> sint = fix fact(n: sint): sint => if n <= 1 then 1 else n * fact(n - 1) in fact(6) end"},"id":2}'
```

```json
{"jsonrpc": "2.0", "id": 2, "result": {"type": "sint", "value": "720"}}
```

### Unbound variable: rejected by the LAMBDA3 type-checker

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"x + 1"},"id":"unbound"}'
```

```json
{"jsonrpc": "2.0", "id": "unbound", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"kind": "type_error", "detail": "unbound variable 'x'"}}}
```

Nothing was interpreted: the type-checker rejected the program first.

### Type error

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"1 + true"},"id":"type"}'
```

```json
{"jsonrpc": "2.0", "id": "type", "error": {"code": -32011, "message": "LAMBDA type error", "data": {"kind": "type_error", "detail": "+: expected bool, got sint"}}}
```

The `detail` text is LAMBDA3's own message, passed through unchanged (see RPC.md 5.2 on its wording).

### Syntax error

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.typecheck","params":{"source":"if then"},"id":"syntax"}'
```

```json
{"jsonrpc": "2.0", "id": "syntax", "error": {"code": -32010, "message": "LAMBDA syntax error", "data": {"kind": "syntax_error", "detail": "Expected an expression", "line": 1, "column": 4, "text": "if then"}}}
```

### `lambda.compile`: Python

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.compile","params":{"source":"1 + 2","target":"python"},"id":"c-py"}'
```

The response is `{"jsonrpc": "2.0", "id": "c-py", "result": {"target": "python", "code": "..."}}`. The `code` string is 4,872 characters: LAMBDA3's runtime preamble followed by the compiled expression. It ends with:

```python
def _lambda_main():
    _v1 = 1
    _v2 = 2
    _v3 = (_v1 + _v2)
    return _v3

_lambda_result = _lambda_main()
```

To see only the code, pipe the response through `python3 -c "import json,sys; print(json.load(sys.stdin)['result']['code'])"`.

### `lambda.compile`: JavaScript

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.compile","params":{"source":"1 + 2","target":"javascript"},"id":"c-js"}'
```

`result.target` is `"javascript"` and `result.code` is 4,996 characters, ending with:

```javascript
function _lambda_main() {
  let _v1 = 1;
  let _v2 = 2;
  let _v3 = (_v1 + _v2);
  return _v3;
}
const _lambda_result = _lambda_main();
```

Again: the service returns this text and does not run it. Running it is up to the client.

### Batch with a notification and an invalid item

```bash
curl -s -i -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '[{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"6 * 7"},"id":"answer"},{"jsonrpc":"2.0","method":"service.health","params":{}},42]'
```

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

[{"jsonrpc": "2.0", "id": "answer", "result": {"type": "sint", "value": "42"}}, {"jsonrpc": "2.0", "id": null, "error": {"code": -32600, "message": "Invalid Request", "data": {"reason": "not_an_object"}}}]
```

The notification (no `id`) produced no entry. Match entries by `id`, not by position.

### Notification-only batch

```bash
curl -s -i -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '[{"jsonrpc":"2.0","method":"service.health","params":{}}]'
```

```
HTTP/1.1 204 NO CONTENT
```

No body.

### Runtime error and timeout

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"1 / 0"},"id":"div"}'
```

```json
{"jsonrpc": "2.0", "id": "div", "error": {"code": -32013, "message": "LAMBDA runtime error", "data": {"kind": "division_by_zero"}}}
```

A doubly recursive `fib(35)` runs for minutes in this interpreter. The service stops it at the deadline (the reply arrived after 5.05 s):

```bash
curl -s -X POST http://127.0.0.1:8000/rpc -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"lambda.interpret","params":{"source":"let fib : sint -> sint = fix fib(n: sint): sint => if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(35) end"},"id":"slow"}'
```

```json
{"jsonrpc": "2.0", "id": "slow", "error": {"code": -32012, "message": "Execution timeout", "data": {"kind": "timeout", "limit_seconds": 5}}}
```

A timeout does not prove the program never terminates. It only means it did not finish within 5 seconds.

## HTTP status vs RPC outcome

Every JSON-RPC response is sent with HTTP **200**, including parse errors, invalid requests and every kind of RPC error. HTTP **204** with an empty body means there was nothing to answer: a single notification, or a batch of only notifications. Other statuses are transport failures that never reach the JSON-RPC layer: **404** for other paths, **405** for verbs other than POST, **413** for bodies over 1 MiB, and **415** for a non-JSON `Content-Type`. RPC.md section 3 has the full decision table.

## Limits

| Limit | Value |
| --- | --- |
| `source` length | 10,000 characters (`-32602`, reason `too_long`) |
| Request body | 1 MiB (HTTP 413) |
| Batch size | 10 items (`-32600`, reason `batch_too_large`) |
| Execution deadline | 5 s per source call, covering parse, type-check and evaluate/compile (`-32012`) |

The reasoning behind each number is in RPC.md section 6.

## Known limitations

- Each source call starts a fresh worker process (the `spawn` start method), which adds roughly 50 ms of start-up. The 5 s clock starts only after the worker is ready.
- The worker memory ceiling (1 GiB, which maps to `-32013` kind `memory_limit`) is set only on Linux. On macOS it is not enforced.
- Batch items run one after another, so a batch of 10 slow calls can take up to 50 s.
- The `mylib/*.lam` library files are declaration files, so they are not reachable through the four methods, which each take one expression.
- `Allow` on a 405 response is `POST, OPTIONS`. Flask adds `OPTIONS` automatically.
