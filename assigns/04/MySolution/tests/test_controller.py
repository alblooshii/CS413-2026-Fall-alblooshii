"""Controller tests with a substituted test backend (view code untouched)."""
import threading
import unittest

from lambda_ui.backend import Lambda1Backend
from lambda_ui.contract import (Artifact, LanguageBackend, Operation, Outcome,
                                Result)
from lambda_ui.controller import Controller
from lambda_ui.model import AppModel
from lambda_ui.view import present

CANNED = {"one": ("One (canned)", "D0Eint(1)")}


class FakeBackend:
    """Records calls; behaviour is injectable."""

    def __init__(self):
        self.calls = []
        self.on_call = None          # optional hook run inside every call
        self.fail_next = None        # exception to raise once
        self.compile_ok = False

    def _do(self, op, arg, revision):
        self.calls.append((op, arg))
        if self.on_call:
            self.on_call(op)
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc
        return Result(op, revision, Outcome.SUCCESS, f"fake {op.value}")

    def lint(self, s): return self._do(Operation.LINT, s, s.revision)
    def interpret(self, s): return self._do(Operation.INTERPRET, s, s.revision)
    def typecheck(self, s): return self._do(Operation.TYPECHECK, s, s.revision)

    def compile(self, s):
        r = self._do(Operation.COMPILE, s, s.revision)
        if self.compile_ok:
            return Result(r.operation, r.revision, r.outcome, r.message,
                          Artifact(s.revision, "fake", "CODE"))
        return r

    def execute(self, a): return self._do(Operation.EXECUTE, a, a.revision)


def make(backend=None):
    model = AppModel()
    backend = backend or FakeBackend()
    return model, backend, Controller(model, backend, CANNED)


class Dispatch(unittest.TestCase):
    def test_fake_satisfies_protocol(self):
        self.assertIsInstance(FakeBackend(), LanguageBackend)
        self.assertIsInstance(Lambda1Backend(), LanguageBackend)

    def test_each_button_reaches_the_matching_backend_operation(self):
        _, be, c = make()
        c.load_canned("one")
        for op in (Operation.LINT, Operation.INTERPRET, Operation.TYPECHECK, Operation.COMPILE):
            self.assertTrue(c.run(op.value).ok)
        self.assertEqual([call[0] for call in be.calls],
                         [Operation.LINT, Operation.INTERPRET, Operation.TYPECHECK, Operation.COMPILE])
        self.assertEqual(be.calls[0][1].text, "D0Eint(1)")
        r = c.state().results
        self.assertEqual([x.operation for x in r],
                         [Operation.COMPILE, Operation.TYPECHECK, Operation.INTERPRET, Operation.LINT])

    def test_unknown_action_and_no_source(self):
        _, be, c = make()
        self.assertEqual(c.run("explode").code, "unknown_action")
        n = c.run("lint")
        self.assertFalse(n.ok)
        self.assertEqual(n.code, "no_source")
        self.assertEqual(be.calls, [])

    def test_view_works_unchanged_with_test_backend(self):
        _, _, c = make()
        c.load_canned("one"); c.run("lint")
        notice = c.run("interpret")
        vm = present(c.state(), notice)
        self.assertEqual([a["label"] for a in vm["actions"]],
                         ["Lint", "Interpret", "Type-check", "Compile", "Execute"])
        self.assertIn("Interpret · revision 1", vm["results"][0]["title"])


class RealPlaceholders(unittest.TestCase):
    def test_placeholders_not_reported_as_success_and_execute_unavailable(self):
        model = AppModel()
        c = Controller(model, Lambda1Backend(), CANNED)
        c.load_canned("one")
        c.run("typecheck"); c.run("compile")
        for res in c.state().results:
            self.assertEqual(res.outcome, Outcome.NOT_IMPLEMENTED)
            self.assertIsNone(res.artifact)
        s = c.state()
        self.assertFalse(s.availability[Operation.EXECUTE].enabled)
        self.assertIsNone(s.artifact)
        n = c.run("execute")
        self.assertFalse(n.ok)
        self.assertEqual(n.code, "not_available")
        vm = present(s)
        self.assertIn("Not implemented", vm["results"][0]["outcome_label"])
        self.assertIn("generated", vm["execute_help"])


class ExecuteAndArtifacts(unittest.TestCase):
    def test_artifact_lifecycle_with_test_compiler(self):
        _, be, c = make()
        be.compile_ok = True
        c.load_canned("one")
        c.run("compile")
        self.assertTrue(c.state().availability[Operation.EXECUTE].enabled)
        self.assertTrue(c.run("execute").ok)
        self.assertEqual(be.calls[-1][1].payload, "CODE")      # consumed the artifact
        self.assertEqual(sum(1 for op, _ in be.calls if op is Operation.COMPILE), 1)  # no silent recompile
        c.edit("D0Eint(2)"); c.apply()                         # source change
        self.assertIsNone(c.state().artifact)
        self.assertFalse(c.run("execute").ok)
        c.run("compile")                                       # recompile OK
        self.assertIsNotNone(c.state().artifact)
        be.compile_ok = False
        c.run("compile")                                       # now "fails": invalidated
        self.assertIsNone(c.state().artifact)


class FailuresBusyAndRetry(unittest.TestCase):
    def test_backend_exception_is_reported_then_retry_succeeds(self):
        model, be, c = make()
        c.load_canned("one")
        be.fail_next = ConnectionError("compiler unreachable")
        n = c.run("interpret")
        self.assertTrue(n.ok)
        s = c.state()
        self.assertEqual(s.results[0].outcome, Outcome.BACKEND_FAILURE)
        self.assertIn("compiler unreachable", s.results[0].message)
        self.assertIsNone(s.busy)                       # controls restored
        self.assertEqual(s.source.text, "D0Eint(1)")    # source preserved
        c.run("interpret")                              # retry
        self.assertEqual(c.state().results[0].outcome, Outcome.SUCCESS)

    def test_timeout_style_failure_result_then_retry(self):
        class Flaky(FakeBackend):
            n = 0
            def interpret(self, s):
                Flaky.n += 1
                if Flaky.n == 1:
                    return Result(Operation.INTERPRET, s.revision, Outcome.BACKEND_FAILURE,
                                  "Timed out after 5 s")
                return super().interpret(s)
        _, _, c = make(Flaky())
        c.load_canned("one")
        c.run("interpret"); c.run("interpret")
        outs = [r.outcome for r in c.state().results]
        self.assertEqual(outs, [Outcome.SUCCESS, Outcome.BACKEND_FAILURE])

    def test_malformed_backend_result_is_a_failure(self):
        class Wrong(FakeBackend):
            def lint(self, s):
                return Result(Operation.INTERPRET, s.revision, Outcome.SUCCESS, "wrong op")
        _, _, c = make(Wrong())
        c.load_canned("one"); c.run("lint")
        self.assertEqual(c.state().results[0].outcome, Outcome.BACKEND_FAILURE)

    def test_busy_state_blocks_conflicting_requests_then_restores(self):
        model, be, c = make()
        c.load_canned("one")
        seen = {}

        def during(op):
            seen["state"] = c.state()
            seen["second"] = c.run("lint")
            seen["edit"] = c.edit("D0Eint(9)")
            seen["apply"] = c.apply("D0Eint(9)")
            seen["load"] = c.load_canned("one")
        be.on_call = during
        c.run("interpret")
        self.assertEqual(seen["state"].busy, Operation.INTERPRET)
        for key in ("second", "edit", "apply", "load"):
            self.assertFalse(seen[key].ok, key)
            self.assertEqual(seen[key].code, "busy", key)
        after = c.state()
        self.assertIsNone(after.busy)
        self.assertEqual(after.source.text, "D0Eint(1)")
        self.assertEqual(len(after.results), 1)

    def test_state_readable_from_another_thread_while_busy(self):
        _, be, c = make()
        c.load_canned("one")
        entered, release = threading.Event(), threading.Event()
        be.on_call = lambda op: (entered.set(), release.wait(5))
        t = threading.Thread(target=lambda: c.run("lint"))
        t.start()
        self.assertTrue(entered.wait(5))
        self.assertEqual(c.state().busy, Operation.LINT)   # page can still poll
        release.set(); t.join(5)
        self.assertIsNone(c.state().busy)


class SourceFlow(unittest.TestCase):
    def test_upload_rejection_keeps_applied_source(self):
        _, _, c = make()
        c.load_canned("one")
        n = c.load_upload("bad.txt", b"\xff\xfe")
        self.assertFalse(n.ok); self.assertEqual(n.code, "bad_encoding")
        self.assertEqual(c.state().source.name, "One (canned)")
        self.assertTrue(c.load_upload("good.txt", b"D0Eint(3)").ok)
        self.assertEqual((c.state().source.name, c.state().revision), ("good.txt", 2))

    def test_load_lint_interpret_trace_with_real_backend(self):
        c = Controller(AppModel(), Lambda1Backend(), CANNED)
        c.load_upload("open.txt", b'D0Evar("x")')
        c.run("lint"); c.run("interpret")
        lint, interp = c.state().results[1], c.state().results[0]
        self.assertEqual((lint.outcome, lint.message), (Outcome.LANGUAGE_ERROR, "Undeclared variable(s): x"))
        self.assertEqual(interp.outcome, Outcome.RUNTIME_ERROR)
        c.edit('D0Elet("x", D0Eint(1), D0Evar("x"))'); c.apply()
        self.assertEqual(c.state().results, ())            # revision 2 cleared old results
        c.run("lint")
        self.assertEqual(c.state().results[0].outcome, Outcome.SUCCESS)


if __name__ == "__main__":
    unittest.main()
