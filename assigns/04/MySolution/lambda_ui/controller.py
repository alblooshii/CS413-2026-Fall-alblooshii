"""Controller: turns user intentions into model changes and backend calls.

No HTTP, HTML or language analysis here. The controller is constructed with
an ``AppModel`` and any object implementing ``contract.LanguageBackend``, so a
test backend can be substituted without touching the view.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import LanguageBackend, Operation, Outcome, Result
from .model import AppModel, ModelState, RuleViolation, Ticket


@dataclass(frozen=True)
class Notice:
    """Immediate feedback on a user request (shown by the view)."""
    ok: bool
    message: str
    code: str = ""


class Controller:
    def __init__(self, model: AppModel, backend: LanguageBackend,
                 canned: dict[str, tuple[str, str]] | None = None) -> None:
        """``canned`` maps a key to (display name, source text)."""
        self.model = model
        self.backend = backend
        self.canned = dict(canned or {})

    # ------------------------------------------------------------------ state
    def state(self) -> ModelState:
        return self.model.snapshot()

    # --------------------------------------------------------- source changes
    def _guard(self, fn, success: str) -> Notice:
        try:
            fn()
        except RuleViolation as exc:
            return Notice(False, exc.message, exc.code)
        return Notice(True, success)

    def load_canned(self, key: str) -> Notice:
        if key not in self.canned:
            return Notice(False, f"Unknown example {key!r}.", "unknown_example")
        name, text = self.canned[key]
        return self._guard(lambda: self.model.load_text(name, text),
                           f"Loaded {name}.")

    def load_upload(self, filename: str, raw: bytes) -> Notice:
        name = filename or "uploaded file"
        return self._guard(lambda: self.model.load_upload(name, raw),
                           f"Loaded {name}.")

    def open_manual(self) -> Notice:
        return self._guard(self.model.begin_manual,
                           "Manual input: type code, then press Apply changes.")

    def edit(self, text: str) -> Notice:
        return self._guard(lambda: self.model.set_draft(text), "Draft saved.")

    def apply(self, text: str | None = None) -> Notice:
        notice = self._guard(lambda: self.model.apply(text), "Changes applied.")
        if notice.ok:
            return Notice(True, f"Changes applied as revision "
                                f"{self.model.snapshot().revision}.")
        return notice

    def discard(self) -> Notice:
        return self._guard(self.model.discard, "Unapplied edits discarded.")

    # ---------------------------------------------------------------- actions
    def run(self, operation: Operation | str) -> Notice:
        try:
            op = Operation(operation)
        except ValueError:
            return Notice(False, f"Unknown action {operation!r}.", "unknown_action")
        try:
            ticket = self.model.begin(op)
        except RuleViolation as exc:
            return Notice(False, exc.message, exc.code)
        result = self._call_backend(ticket)
        self.model.finish(ticket, result)
        return Notice(True, f"{op.value} finished.", result.outcome.value)

    def _call_backend(self, ticket: Ticket) -> Result:
        op = ticket.operation
        try:
            if op is Operation.EXECUTE:
                result = self.backend.execute(ticket.artifact)
            else:
                result = getattr(self.backend, op.value)(ticket.source)
            if (not isinstance(result, Result) or result.operation is not op
                    or result.revision != ticket.revision):
                raise TypeError("backend returned a result for the wrong "
                                "operation or revision")
            return result
        except Exception as exc:     # noqa: BLE001 - backend must never wedge UI
            return Result(op, ticket.revision, Outcome.BACKEND_FAILURE,
                          f"The language tool failed: {type(exc).__name__}: "
                          f"{exc}. Your source is unchanged; you can retry.")
