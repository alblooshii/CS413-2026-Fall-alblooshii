"""Real Lint and Interpret through the adapter (worker process), plus placeholders."""
import unittest
from pathlib import Path
from unittest import mock

import lambda1
from lambda_ui import worker
from lambda_ui.backend import Lambda1Backend
from lambda_ui.contract import Artifact, Operation, Outcome, Source

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def src(text, rev=1):
    return Source("t", text, rev)


def fact(n):
    return (SAMPLES / "factorial.txt").read_text().replace("D0Eint(10))", f"D0Eint({n}))")


def fib(n):
    return (SAMPLES / "fibonacci.txt").read_text().replace("D0Eint(10))", f"D0Eint({n}))")


class LintTests(unittest.TestCase):
    backend = Lambda1Backend()

    def test_closed_program_passes(self):
        r = self.backend.lint(src('D0Elam("x", D0Evar("x"))', 7))
        self.assertEqual((r.operation, r.revision, r.outcome),
                         (Operation.LINT, 7, Outcome.SUCCESS))
        self.assertIn("No free variables", r.message)

    def test_open_program_lists_names_deterministically(self):
        text = 'D0Eop2("+", D0Evar("zeta"), D0Eop2("+", D0Evar("alpha"), D0Evar("zeta")))'
        r = self.backend.lint(src(text))
        self.assertEqual(r.outcome, Outcome.LANGUAGE_ERROR)
        self.assertEqual(r.message, "Undeclared variable(s): alpha, zeta")

    def test_lint_does_not_evaluate(self):
        # Closed but fails at run time; Lint passes, Interpret fails.
        text = 'D0Eop2("/", D0Eint(1), D0Eint(0))'
        self.assertEqual(self.backend.lint(src(text)).outcome, Outcome.SUCCESS)
        self.assertEqual(self.backend.interpret(src(text)).outcome, Outcome.RUNTIME_ERROR)

    def test_lint_never_calls_evaluate_in_process(self):
        with mock.patch.object(lambda1, "d0exp_evaluate",
                               side_effect=AssertionError("evaluated!")) as ev:
            out = worker.lint('D0Eop2("/", D0Eint(1), D0Eint(0))')
        self.assertEqual(out["outcome"], "success")
        ev.assert_not_called()

    def test_malformed_input(self):
        r = self.backend.lint(src('D0Eop2("+", D0Eint(1)'))
        self.assertEqual(r.outcome, Outcome.INPUT_ERROR)


class InterpretTests(unittest.TestCase):
    backend = Lambda1Backend()

    def val(self, text):
        r = self.backend.interpret(src(text))
        self.assertEqual(r.outcome, Outcome.SUCCESS, r.message)
        return r.message

    def test_arithmetic(self):
        self.assertEqual(self.val('D0Eop2("+", D0Eint(20), D0Eint(22))'), "D0Vint(arg1=42)")
        self.assertEqual(self.val('D0Eop2("<", D0Eint(1), D0Eint(2))'), "D0Vbtf(arg1=True)")

    def test_pair_value(self):
        self.assertEqual(self.val("D0Epair(D0Eint(1), D0Ebtf(False))"),
                         "D0Vpair(arg1=D0Vint(arg1=1), arg2=D0Vbtf(arg1=False))")

    def test_factorial_including_base_cases(self):
        for n, want in [(0, 1), (1, 1), (5, 120), (10, 3628800)]:
            self.assertEqual(self.val(fact(n)), f"D0Vint(arg1={want})")

    def test_fibonacci_including_base_cases(self):
        for n, want in [(0, 0), (1, 1), (2, 1), (10, 55)]:
            self.assertEqual(self.val(fib(n)), f"D0Vint(arg1={want})")

    def test_malformed_input_is_input_error(self):
        for text in ['D0Eint(', 'print(1)', '   # only a comment', 'D0Eint("a")']:
            r = self.backend.interpret(src(text))
            self.assertEqual(r.outcome, Outcome.INPUT_ERROR, text)

    def test_runtime_failures_are_runtime_errors(self):
        cases = {
            "division by zero": 'D0Eop2("/", D0Eint(1), D0Eint(0))',
            "unbound variable (D0V000)": 'D0Evar("x")',
            "D0V000 inside a pair": 'D0Epair(D0Eint(1), D0Evar("x"))',
            "type error": 'D0Eop2("+", D0Eint(1), D0Ebtf(True))',
            "apply non-function": 'D0Eapp(D0Eint(1), D0Eint(2))',
            "unsupported operator": 'D0Eop2("%", D0Eint(1), D0Eint(2))',
            "non-boolean condition": 'D0Eif0(D0Eint(1), D0Eint(1), D0Eint(2))',
        }
        for label, text in cases.items():
            r = self.backend.interpret(src(text))
            self.assertEqual(r.outcome, Outcome.RUNTIME_ERROR, label)
            self.assertTrue(r.message.startswith("Runtime error"), label)

    def test_endless_recursion_reports_runtime_error(self):
        loop = ('D0Eapp(D0Efix("f", "x", D0Eapp(D0Evar("f"), D0Evar("x"))), D0Eint(0))')
        r = self.backend.interpret(src(loop))
        self.assertEqual(r.outcome, Outcome.RUNTIME_ERROR)
        self.assertIn("recursion", r.message)

    def test_html_like_text_is_returned_verbatim(self):
        r = self.backend.interpret(src('D0Ebtf(True)  # <b>x</b>'))
        self.assertEqual(r.message, "D0Vbtf(arg1=True)")

    def test_timeout_stops_long_computation(self):
        slow = Lambda1Backend(timeout=1.5)
        r = slow.interpret(src(fib(32)))          # exponential: far beyond 1.5 s
        self.assertEqual(r.outcome, Outcome.BACKEND_FAILURE)
        self.assertIn("Timed out", r.message)

    def test_worker_crash_is_backend_failure(self):
        with mock.patch("lambda_ui.backend.subprocess.run", side_effect=OSError("boom")):
            r = self.backend.interpret(src("D0Eint(1)"))
        self.assertEqual(r.outcome, Outcome.BACKEND_FAILURE)
        with mock.patch("lambda_ui.backend.subprocess.run") as run:
            run.return_value = mock.Mock(stdout="", stderr="Traceback\nKaboom", returncode=1)
            r = self.backend.lint(src("D0Eint(1)"))
        self.assertEqual(r.outcome, Outcome.BACKEND_FAILURE)
        self.assertIn("Kaboom", r.message)


class PlaceholderTests(unittest.TestCase):
    backend = Lambda1Backend()

    def test_typecheck_and_compile_are_not_implemented(self):
        s = src("D0Eint(1)", 3)
        tc, co = self.backend.typecheck(s), self.backend.compile(s)
        self.assertEqual((tc.operation, tc.revision, tc.outcome),
                         (Operation.TYPECHECK, 3, Outcome.NOT_IMPLEMENTED))
        self.assertEqual((co.operation, co.revision, co.outcome),
                         (Operation.COMPILE, 3, Outcome.NOT_IMPLEMENTED))
        self.assertIn("not yet implemented", tc.message)
        self.assertIn("not yet implemented", co.message)
        self.assertIsNone(co.artifact)

    def test_execute_does_not_interpret(self):
        r = self.backend.execute(Artifact(1, "python", "print(1)"))
        self.assertEqual(r.outcome, Outcome.NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
