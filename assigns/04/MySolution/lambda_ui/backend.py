"""Language-tool adapter: the only module that knows how tools are invoked.

``Lambda1Backend`` implements ``contract.LanguageBackend``. Lint and Interpret
run the real ``lambda1`` functions inside a short-lived worker process with a
timeout; Type-check and Compile are honest placeholders; Execute is reserved
for compiler-generated artifacts and refuses to run anything else.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .contract import Artifact, Operation, Outcome, Result, Source

DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("LAMBDA_UI_TIMEOUT", "5"))
_PROJECT_ROOT = Path(__file__).resolve().parent.parent   # holds lambda1.py


class Lambda1Backend:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    # ----------------------------------------------------------- real tools
    def lint(self, source: Source) -> Result:
        return self._run_worker(Operation.LINT, source)

    def interpret(self, source: Source) -> Result:
        return self._run_worker(Operation.INTERPRET, source)

    # ---------------------------------------------------------- placeholders
    def typecheck(self, source: Source) -> Result:
        return Result(Operation.TYPECHECK, source.revision,
                      Outcome.NOT_IMPLEMENTED,
                      "Type checking is not yet implemented.")

    def compile(self, source: Source) -> Result:
        return Result(Operation.COMPILE, source.revision,
                      Outcome.NOT_IMPLEMENTED,
                      "Compilation is not yet implemented. Execute runs code "
                      "produced by Compile, so it stays unavailable until "
                      "compilation exists and has produced an artifact.")

    def execute(self, artifact: Artifact) -> Result:
        return Result(Operation.EXECUTE, artifact.revision,
                      Outcome.NOT_IMPLEMENTED,
                      "Execution of generated code is not yet implemented.")

    # --------------------------------------------------------------- helpers
    def _run_worker(self, op: Operation, source: Source) -> Result:
        request = json.dumps({"op": op.value, "source": source.text})
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "lambda_ui.worker"],
                input=request, capture_output=True, text=True,
                timeout=self.timeout, cwd=_PROJECT_ROOT)
        except subprocess.TimeoutExpired:
            return Result(op, source.revision, Outcome.BACKEND_FAILURE,
                          f"Timed out after {self.timeout:g} s; the worker "
                          "was stopped. The program may not terminate.")
        except OSError as exc:
            return Result(op, source.revision, Outcome.BACKEND_FAILURE,
                          f"Could not start the language tool: {exc}")
        try:
            data = json.loads(proc.stdout)
            outcome = Outcome(data["outcome"])
            message = str(data["message"])
        except (ValueError, KeyError):
            detail = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
            return Result(op, source.revision, Outcome.BACKEND_FAILURE,
                          f"The language tool failed (exit code "
                          f"{proc.returncode}): {detail[0]}")
        return Result(op, source.revision, outcome, message)
