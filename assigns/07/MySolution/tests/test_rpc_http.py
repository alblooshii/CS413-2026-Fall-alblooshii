"""HTTP-level tests for the JSON-RPC service, through Flask's test client.

Success paths run real LAMBDA3 in real worker processes. Test doubles are used
only for backend failure and timeout. Run from assigns/07:

    MySolution/.venv/bin/python -m unittest discover -s MySolution/tests -v
"""

import json
import math
import multiprocessing
import sys
import time
import unittest
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rpc_service import lambda_service, runner  # noqa: E402
from rpc_service.app import create_app  # noqa: E402

FACT = ("let fact : sint -> sint =\n  fix fact(n: sint): sint =>\n"
        "    if n <= 1 then 1 else n * fact(n - 1)\nin fact(6) end")
FIB35 = ("let fib : sint -> sint = fix fib(n: sint): sint => "
         "if n < 2 then n else fib(n - 1) + fib(n - 2) in fib(35) end")


def req(method, params=None, id=1, **extra):
    body = {"jsonrpc": "2.0", "method": method, **extra}
    if params is not None:
        body["params"] = params
    if id is not ...:
        body["id"] = id
    return body


class Base(unittest.TestCase):
    backend = None  # None = real worker processes

    @classmethod
    def setUpClass(cls):
        cls.client = create_app(cls.backend).test_client()

    def post(self, payload=None, *, raw=None, content_type="application/json"):
        data = raw if raw is not None else json.dumps(payload)
        resp = self.client.post("/rpc", data=data, content_type=content_type)
        body = json.loads(resp.data) if resp.data else None
        return resp, body

    def call(self, method, params=None, id=1):
        resp, body = self.post(req(method, params, id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json; charset=utf-8")
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["id"], id)
        self.assertNotEqual("result" in body, "error" in body)  # exactly one
        return body

    def ok(self, method, params=None, id=1):
        body = self.call(method, params, id)
        self.assertIn("result", body, body)
        return body["result"]

    def err(self, method, params, code, id=1):
        body = self.call(method, params, id)
        self.assertIn("error", body, body)
        self.assertEqual(body["error"]["code"], code, body)
        self.assertIsInstance(body["error"]["message"], str)
        return body["error"]


class HealthAndTypecheck(Base):
    def test_health_returns_version_and_preserves_id(self):
        for rid in ("health-1", 7, None):
            with self.subTest(id=rid):
                self.assertEqual(self.ok("service.health", {}, rid), {"status": "ok", "version": "1.0"})

    def test_health_params_may_be_omitted(self):
        self.assertEqual(self.ok("service.health"), {"status": "ok", "version": "1.0"})

    def test_typecheck_valid_programs(self):
        for source, typ in [("1 + 2", "sint"), (FACT, "sint"), ("(1, true)", "(sint, bool)"),
                            ("lam (x: sint) => x", "sint -> sint"), ("true", "bool"),
                            ("list_cons(1, list_nil())", "List[sint]")]:
            with self.subTest(source=source[:30]):
                self.assertEqual(self.ok("lambda.typecheck", {"source": source}), {"type": typ})

    def test_unbound_variable_is_rejected_by_lambda3_typechecker(self):
        error = self.err("lambda.interpret", {"source": "x + 1"}, -32011)
        self.assertEqual(error["data"], {"kind": "type_error", "detail": "unbound variable 'x'"})


class Interpret(Base):
    def test_arithmetic(self):
        self.assertEqual(self.ok("lambda.interpret", {"source": "20 + 22"}), {"type": "sint", "value": "42"})

    def test_factorial(self):
        self.assertEqual(self.ok("lambda.interpret", {"source": FACT}), {"type": "sint", "value": "720"})

    def test_tuple(self):
        self.assertEqual(self.ok("lambda.interpret", {"source": "(1, true)"}),
                         {"type": "(sint, bool)", "value": "(1, true)"})

    def test_collections(self):
        for source, typ, value in [
            ("list_cons(1, list_cons(2, list_nil()))", "List[sint]", "[1, 2]"),
            ("a1sz_make_ncpy(3, 7)", "A1sz[sint]", "[7, 7, 7]"),
            ("optn_cons(1)", "Optn[sint]", "optn_cons(1)"),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self.ok("lambda.interpret", {"source": source}), {"type": typ, "value": value})

    def test_function_value_does_not_leak_closure(self):
        result = self.ok("lambda.interpret", {"source": "let f : sint -> sint = lam (x: sint) => x in f end"})
        self.assertEqual(result, {"type": "sint -> sint", "value": "<lam>"})
        fix = self.ok("lambda.interpret", {"source": "fix f(n: sint): sint => n"})
        self.assertEqual(fix["value"], "<fix>")

    def test_print_output_is_discarded(self):
        self.assertEqual(self.ok("lambda.interpret", {"source": "print(5)"}), {"type": "unit", "value": "()"})

    def test_large_integer_keeps_precision(self):
        source = ("let f : sint -> sint = fix f(n: sint): sint => if n <= 1 then 1 else n * f(n - 1) in f(90) end")
        value = self.ok("lambda.interpret", {"source": source})["value"]
        self.assertEqual(value, str(math.factorial(90)))


class Compile(Base):
    def test_python_and_javascript_return_unchanged_lambda3_output(self):
        expr = lambda_service.L.d0exp_parse("1 + 2")
        expected = {"python": lambda_service.L.d0exp_compile(expr),
                    "javascript": lambda_service.L.d0exp_compile_js(expr)}
        for target in ("python", "javascript"):
            with self.subTest(target=target):
                result = self.ok("lambda.compile", {"source": "1 + 2", "target": target})
                self.assertEqual(result["target"], target)
                self.assertEqual(result["code"], expected[target])
                self.assertIn("_lambda_main", result["code"])

    def test_compile_still_type_checks_first(self):
        self.err("lambda.compile", {"source": "x + 1", "target": "python"}, -32011)
        self.err("lambda.compile", {"source": "1 +", "target": "javascript"}, -32010)


class LambdaErrors(Base):
    def test_syntax_and_type_errors_have_distinct_codes_and_data(self):
        syntax = self.err("lambda.typecheck", {"source": "if then"}, -32010)
        self.assertEqual(syntax["message"], "LAMBDA syntax error")
        self.assertEqual(syntax["data"], {"kind": "syntax_error", "detail": "Expected an expression",
                                          "line": 1, "column": 4, "text": "if then"})
        typ = self.err("lambda.typecheck", {"source": "1 + true"}, -32011)
        self.assertEqual(typ["data"]["kind"], "type_error")
        self.assertNotIn("line", typ["data"])

    def test_multiline_syntax_error_position(self):
        data = self.err("lambda.typecheck", {"source": "let x = 1\nin x +\nend"}, -32010)["data"]
        self.assertEqual((data["line"], data["column"], data["text"]), (3, 1, "end"))
        self.assertNotIn("<lambda>", json.dumps(data))

    def test_runtime_errors_are_their_own_code(self):
        for source, kind in [("1 / 0", "division_by_zero"),
                             ("list_head(list_nil())", "invalid_operation"),
                             ("a1sz_getat(a1sz_make_ncpy(2, 0), 5)", "index_out_of_range")]:
            with self.subTest(source=source):
                error = self.err("lambda.interpret", {"source": source}, -32013)
                self.assertEqual((error["message"], error["data"]), ("LAMBDA runtime error", {"kind": kind}))

    def test_deep_recursion_is_recursion_limit_not_internal(self):
        source = ("let f : sint -> sint = fix f(n: sint): sint => if n <= 1 then 1 else n * f(n - 1) in f(500) end")
        self.assertEqual(self.err("lambda.interpret", {"source": source}, -32013)["data"], {"kind": "recursion_limit"})

    def test_deeply_nested_parentheses_in_typecheck(self):
        source = "(" * 500 + "1" + ")" * 500
        self.assertEqual(self.err("lambda.typecheck", {"source": source}, -32013)["data"], {"kind": "recursion_limit"})

    def test_no_traceback_or_path_in_any_lambda_error(self):
        for source in ("if then", "x + 1", "1 / 0"):
            body = json.dumps(self.call("lambda.interpret", {"source": source}))
            for banned in ("Traceback", "File \"", ".py", "/Users"):
                self.assertNotIn(banned, body)


class ParamsAndEnvelope(Base):
    def test_param_validation(self):
        cases = [
            ("lambda.interpret", {"source": "   "}, "blank"),
            ("lambda.interpret", {"source": ""}, "blank"),
            ("lambda.interpret", {"source": 12}, "wrong_type"),
            ("lambda.interpret", {"source": None}, "wrong_type"),
            ("lambda.interpret", {}, "missing_param"),
            ("lambda.interpret", None, "missing_param"),
            ("lambda.interpret", ["1"], "params_must_be_object"),
            ("lambda.interpret", {"source": "1", "sourc": "2"}, "unexpected_param"),
            ("lambda.compile", {"source": "1"}, "missing_param"),
            ("lambda.compile", {"source": "1", "target": "ruby"}, "invalid_value"),
            ("lambda.compile", {"source": "1", "target": "Python"}, "invalid_value"),
            ("lambda.compile", {"source": "1", "target": 3}, "wrong_type"),
            ("lambda.typecheck", {"source": "1", "target": "python"}, "unexpected_param"),
            ("lambda.typecheck", {"source": "\ud800"}, "invalid_unicode"),
            ("service.health", {"x": 1}, "unexpected_param"),
            ("service.health", [], "params_must_be_object"),
        ]
        for method, params, reason in cases:
            with self.subTest(method=method, params=params):
                error = self.err(method, params, -32602)
                self.assertEqual(error["message"], "Invalid params")
                self.assertEqual(error["data"]["reason"], reason)

    def test_source_size_limit_is_exact(self):
        at_limit = "1" + " " * 9_999
        self.assertEqual(self.ok("lambda.typecheck", {"source": at_limit}), {"type": "sint"})
        error = self.err("lambda.typecheck", {"source": at_limit + " "}, -32602)
        self.assertEqual(error["data"], {"reason": "too_long", "param": "source", "max_length": 10000})

    def test_unknown_method_wins_over_bad_params(self):
        self.err("does.not.exist", {"source": 5}, -32601)
        self.err("Lambda.typecheck", {"source": "1"}, -32601)  # case-sensitive

    def test_malformed_json_is_parse_error_with_http_200(self):
        for raw in (b'{"jsonrpc":', b"", b"not json", b'{"jsonrpc":"2.0","id":NaN}', b"[" * 100_000):
            with self.subTest(raw=raw[:20]):
                resp, body = self.post(raw=raw)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(body["id"], None)
                self.assertEqual(body["error"]["code"], -32700)
        resp, body = self.post(raw=b"\xff\xfe")
        self.assertEqual(body["error"]["data"], {"reason": "invalid_utf8"})

    def test_invalid_envelopes_get_invalid_request_with_null_id(self):
        cases = [
            ({"jsonrpc": "1.0", "method": "service.health", "id": 1}, "bad_jsonrpc_version"),
            ({"method": "service.health", "id": 1}, "bad_jsonrpc_version"),
            ({"jsonrpc": "2.0", "id": 1}, "bad_method"),
            ({"jsonrpc": "2.0", "method": 5, "id": 1}, "bad_method"),
            ({"jsonrpc": "2.0", "method": "service.health", "id": True}, "bad_id"),
            ({"jsonrpc": "2.0", "method": "service.health", "id": {}}, "bad_id"),
            ({"jsonrpc": "2.0", "method": "service.health", "id": [1]}, "bad_id"),
            ({"jsonrpc": "2.0", "method": "service.health", "params": 5, "id": 1}, "bad_params_type"),
            ({"jsonrpc": "2.0", "method": "service.health", "params": None, "id": 1}, "bad_params_type"),
            ({"jsonrpc": "2.0", "method": "service.health", "params": "x"}, "bad_params_type"),  # no id: still answered
            (42, "not_an_object"),
            ("x", "not_an_object"),
            (None, "not_an_object"),
        ]
        for payload, reason in cases:
            with self.subTest(payload=payload):
                resp, body = self.post(payload)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(body, {"jsonrpc": "2.0", "id": None,
                                        "error": {"code": -32600, "message": "Invalid Request",
                                                  "data": {"reason": reason}}})

    def test_infinite_float_id_is_invalid(self):
        resp, body = self.post(raw=b'{"jsonrpc":"2.0","method":"service.health","id":1e999}')
        self.assertEqual(body["error"]["data"], {"reason": "bad_id"})

    def test_id_types_are_preserved(self):
        for rid in ("a", "", 0, -5, 2.5, 10**30, None):
            with self.subTest(id=rid):
                self.assertEqual(self.call("service.health", {}, rid)["id"], rid)


class Transport(Base):
    def test_wrong_media_type_is_415_not_a_rpc_response(self):
        for ctype in ("text/plain", "application/xml", "application/json; charset=latin-1"):
            with self.subTest(ctype=ctype):
                resp, body = self.post(raw=b"{}", content_type=ctype)
                self.assertEqual(resp.status_code, 415)
                self.assertNotIn("jsonrpc", body)
        resp = self.client.post("/rpc", data=b"{}")
        self.assertEqual(resp.status_code, 415)

    def test_utf8_charset_parameter_is_accepted(self):
        resp, body = self.post(req("service.health", {}), content_type="application/json; charset=utf-8")
        self.assertEqual(resp.status_code, 200)

    def test_other_verbs_and_paths(self):
        resp = self.client.get("/rpc")
        self.assertEqual(resp.status_code, 405)
        self.assertIn("POST", resp.headers["Allow"])
        self.assertNotIn("GET", resp.headers["Allow"])
        self.assertEqual(self.client.get("/other").status_code, 404)
        self.assertEqual(self.client.post("/other", json={}).status_code, 404)

    def test_oversized_body_is_413(self):
        resp, body = self.post(raw=b" " * (1 << 20) + b"{}")
        self.assertEqual(resp.status_code, 413)
        self.assertNotIn("jsonrpc", body)


class Batches(Base):
    def test_responses_match_by_id_and_omit_notifications(self):
        resp, body = self.post([
            req("lambda.interpret", {"source": "6 * 7"}, "answer"),
            req("service.health", {}, id=...),
            req("lambda.typecheck", {"source": "x + 1"}, 7),
        ])
        self.assertEqual(resp.status_code, 200)
        by_id = {r["id"]: r for r in body}
        self.assertEqual(len(body), 2)
        self.assertEqual(by_id["answer"]["result"], {"type": "sint", "value": "42"})
        self.assertEqual(by_id[7]["error"]["code"], -32011)

    def test_invalid_members_get_null_id_errors_and_others_still_run(self):
        resp, body = self.post([req("service.health", {}, "ok"), 42, {"jsonrpc": "2.0"}, "x"])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(body), 4)
        self.assertEqual({r["id"] for r in body}, {"ok", None})
        nulls = [r for r in body if r["id"] is None]
        self.assertEqual({r["error"]["code"] for r in nulls}, {-32600})
        self.assertEqual(len(nulls), 3)

    def test_notification_only_batch_is_204_with_empty_body(self):
        resp = self.client.post("/rpc", json=[req("service.health", {}, id=...),
                                              req("lambda.typecheck", {"source": "1 + 2"}, id=...)])
        self.assertEqual((resp.status_code, resp.data), (204, b""))
        self.assertIsNone(resp.content_type)

    def test_failing_notifications_stay_silent(self):
        batch = [req("does.not.exist", id=...), req("lambda.typecheck", {"source": "x"}, id=...),
                 req("lambda.typecheck", {"source": 5}, id=...)]
        resp = self.client.post("/rpc", json=batch)
        self.assertEqual((resp.status_code, resp.data), (204, b""))

    def test_single_notification_is_204(self):
        resp = self.client.post("/rpc", json=req("service.health", {}, id=...))
        self.assertEqual((resp.status_code, resp.data), (204, b""))

    def test_null_id_is_a_call_not_a_notification(self):
        resp, body = self.post([req("service.health", {}, None)])
        self.assertEqual((resp.status_code, body[0]["id"]), (200, None))

    def test_empty_batch_is_one_invalid_request_object(self):
        resp, body = self.post([])
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(body, dict)
        self.assertEqual((body["id"], body["error"]["code"], body["error"]["data"]),
                         (None, -32600, {"reason": "empty_batch"}))

    def test_oversized_batch_runs_nothing(self):
        resp, body = self.post([req("service.health", {}, i) for i in range(11)])
        self.assertEqual((resp.status_code, body["error"]["data"]), (200, {"reason": "batch_too_large"}))
        resp, body = self.post([req("service.health", {}, i) for i in range(10)])
        self.assertEqual(len(body), 10)


class Recorder:
    """Backend test double: records calls, then returns / raises as configured."""

    def __init__(self, outcome=None, exc=None):
        self.calls, self.outcome, self.exc = [], outcome, exc

    def __call__(self, op, source, target=None):
        self.calls.append((op, source, target))
        if self.exc:
            raise self.exc
        return self.outcome


class BackendFailures(unittest.TestCase):
    def client(self, backend):
        return create_app(backend).test_client()

    def rpc(self, backend, rid="req-9", method="lambda.interpret"):
        resp = self.client(backend).post("/rpc", json=req(method, {"source": "1"}, rid))
        return resp, json.loads(resp.data)

    def test_unexpected_backend_failure_is_32603_without_details(self):
        secret = RuntimeError("boom /Users/secret/path.py Traceback (most recent call last)")
        with self.assertLogs("rpc_service.jsonrpc", level="ERROR") as logs:
            resp, body = self.rpc(Recorder(exc=secret))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body, {"jsonrpc": "2.0", "id": "req-9",
                                "error": {"code": -32603, "message": "Internal error"}})
        self.assertIn("boom", "\n".join(logs.output))  # logged server-side
        for leaked in ("boom", "secret", "Traceback", ".py"):
            self.assertNotIn(leaked, resp.get_data(as_text=True))

    def test_worker_internal_failure_is_32603_and_logged(self):
        outcome = {"ok": False, "failure": {"kind": "internal", "log": "Traceback ... /Users/x/lambda3.py"}}
        with self.assertLogs("rpc_service.methods", level="ERROR"):
            resp, body = self.rpc(Recorder(outcome=outcome))
        self.assertEqual((body["id"], body["error"]), ("req-9", {"code": -32603, "message": "Internal error"}))
        self.assertNotIn("lambda3.py", resp.get_data(as_text=True))

    def test_timeout_is_32012_and_preserves_id(self):
        resp, body = self.rpc(Recorder(exc=runner.DeadlineExceeded()), rid=123)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["id"], 123)
        self.assertEqual(body["error"], {"code": -32012, "message": "Execution timeout",
                                         "data": {"kind": "timeout", "limit_seconds": 5}})
        self.assertNotIn("result", body)

    def test_invalid_params_never_reach_the_backend(self):
        backend = Recorder(outcome={"ok": True, "result": {}})
        client = self.client(backend)
        for params in ({"source": " "}, {"source": 1}, {}, ["x"]):
            client.post("/rpc", json=req("lambda.interpret", params))
        client.post("/rpc", json=req("nope", {"source": "1"}))
        self.assertEqual(backend.calls, [])

    def test_valid_notification_is_executed_but_silent(self):
        backend = Recorder(outcome={"ok": True, "result": {"type": "sint"}})
        resp = self.client(backend).post("/rpc", json=req("lambda.typecheck", {"source": "1"}, id=...))
        self.assertEqual((resp.status_code, resp.data), (204, b""))
        self.assertEqual(backend.calls, [("typecheck", "1", None)])

    def test_notification_that_crashes_is_silent_and_logged(self):
        with self.assertLogs("rpc_service.jsonrpc", level="ERROR"):
            resp = self.client(Recorder(exc=RuntimeError("x"))).post(
                "/rpc", json=req("lambda.typecheck", {"source": "1"}, id=...))
        self.assertEqual((resp.status_code, resp.data), (204, b""))

    def test_one_failing_batch_item_does_not_affect_others(self):
        calls = iter([RuntimeError("x"), {"ok": True, "result": {"type": "sint"}}])

        def flaky(op, source, target=None):
            item = next(calls)
            if isinstance(item, Exception):
                raise item
            return item

        with self.assertLogs("rpc_service.jsonrpc", level="ERROR"):
            resp = self.client(flaky).post("/rpc", json=[req("lambda.typecheck", {"source": "1"}, "a"),
                                                         req("lambda.typecheck", {"source": "1"}, "b")])
        by_id = {r["id"]: r for r in json.loads(resp.data)}
        self.assertEqual(by_id["a"]["error"]["code"], -32603)
        self.assertEqual(by_id["b"]["result"], {"type": "sint"})


class RealDeadline(unittest.TestCase):
    def test_runaway_computation_is_killed_and_reported_as_timeout(self):
        backend = partial(runner.run_with_deadline, timeout=0.5)
        client = create_app(backend).test_client()
        started = time.monotonic()
        resp = client.post("/rpc", json=req("lambda.interpret", {"source": FIB35}, "slow"))
        elapsed = time.monotonic() - started
        body = json.loads(resp.data)
        self.assertEqual(body["id"], "slow")
        self.assertEqual(body["error"]["code"], -32012)
        self.assertNotIn("result", body)
        self.assertLess(elapsed, 5, "fib(35) takes minutes; the worker must have been killed")
        time.sleep(0.2)
        self.assertEqual(multiprocessing.active_children(), [], "worker process leaked")

    def test_service_still_works_after_a_timeout(self):
        client = create_app(partial(runner.run_with_deadline, timeout=0.5)).test_client()
        client.post("/rpc", json=req("lambda.interpret", {"source": FIB35}))
        body = json.loads(client.post("/rpc", json=req("lambda.interpret", {"source": "1 + 1"})).data)
        self.assertEqual(body["result"], {"type": "sint", "value": "2"})


if __name__ == "__main__":
    unittest.main()
