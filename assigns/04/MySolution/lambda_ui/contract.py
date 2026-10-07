"""The language-tool contract shared by model, controller and backend adapters.

This module has no dependencies on Flask, HTML, lambda1, or any other part of
the application. It only defines data types and the backend interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class Operation(str, Enum):
    LINT = "lint"
    INTERPRET = "interpret"
    TYPECHECK = "typecheck"
    COMPILE = "compile"
    EXECUTE = "execute"


# Display order of the action buttons (F4).
OPERATION_ORDER = (Operation.LINT, Operation.INTERPRET, Operation.TYPECHECK,
                   Operation.COMPILE, Operation.EXECUTE)


class Outcome(str, Enum):
    SUCCESS = "success"                  # operation completed, nothing wrong
    INPUT_ERROR = "input_error"          # source is not a valid constructor expression
    LANGUAGE_ERROR = "language_error"    # valid input, but lint found undeclared variables
    RUNTIME_ERROR = "runtime_error"      # valid input, evaluation failed
    BACKEND_FAILURE = "backend_failure"  # tool crashed, timed out or is unreachable
    NOT_IMPLEMENTED = "not_implemented"  # placeholder operation


@dataclass(frozen=True)
class Source:
    """An applied source: immutable, identified by its revision number."""
    name: str
    text: str
    revision: int


@dataclass(frozen=True)
class Artifact:
    """Generated code produced by Compile and consumed by Execute.

    ``revision`` is the source revision the artifact was compiled from; the
    model drops the artifact as soon as the applied source changes.
    ``kind`` names the code format (e.g. "python", "js") and ``payload`` is the
    generated code itself as text.
    """
    revision: int
    kind: str
    payload: str


@dataclass(frozen=True)
class Result:
    """Outcome of one operation on one source revision."""
    operation: Operation
    revision: int
    outcome: Outcome
    message: str
    artifact: Artifact | None = None   # only Compile may set this


@runtime_checkable
class LanguageBackend(Protocol):
    """Replaceable language-tool interface (see ARCHITECTURE.md)."""

    def lint(self, source: Source) -> Result: ...
    def interpret(self, source: Source) -> Result: ...
    def typecheck(self, source: Source) -> Result: ...
    def compile(self, source: Source) -> Result: ...
    def execute(self, artifact: Artifact) -> Result: ...
