"""Model: owns the applied source, its revision, results and the artifact.

All state rules live here and are enforceable without a browser, templates,
HTTP request objects or a language backend. The model never parses or
interprets LAMBDA code; it only stores the text and the results produced by a
backend (it depends on ``contract`` only).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from types import MappingProxyType

from .contract import (Artifact, OPERATION_ORDER, Operation, Outcome, Result,
                       Source)

MAX_SOURCE_BYTES = 64 * 1024     # documented size limit (UTF-8 bytes)
MAX_RESULTS = 50                 # results kept for the current revision


class RuleViolation(Exception):
    """A state rule was violated; the model state is left unchanged."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Availability:
    enabled: bool
    reason: str = ""      # why disabled (empty when enabled)


@dataclass(frozen=True)
class Ticket:
    """Handed out by ``begin`` and handed back to ``finish``."""
    operation: Operation
    source: Source | None = None       # for every operation except Execute
    artifact: Artifact | None = None   # for Execute

    @property
    def revision(self) -> int:
        return self.source.revision if self.source else self.artifact.revision


@dataclass(frozen=True)
class ModelState:
    """Immutable snapshot handed to the view."""
    source: Source | None
    revision: int
    draft: str | None
    draft_name: str | None
    dirty: bool
    busy: Operation | None
    editor_text: str
    editor_epoch: int
    results: tuple[Result, ...]        # newest first, current revision only
    artifact: Artifact | None
    availability: "MappingProxyType[Operation, Availability]"


class AppModel:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._source: Source | None = None
        self._revision = 0
        self._draft: str | None = None
        self._draft_name: str | None = None
        self._busy: Operation | None = None
        self._results: list[Result] = []
        self._artifact: Artifact | None = None
        self._epoch = 0

    # ------------------------------------------------------------ validation
    @staticmethod
    def validate_text(text: str) -> None:
        if not text.strip():
            raise RuleViolation("empty_source",
                                "Source is empty or contains only whitespace.")
        if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise RuleViolation(
                "too_large",
                f"Source exceeds the {MAX_SOURCE_BYTES}-byte limit.")

    @staticmethod
    def decode_upload(raw: bytes) -> str:
        if len(raw) > MAX_SOURCE_BYTES:
            raise RuleViolation(
                "too_large",
                f"File exceeds the {MAX_SOURCE_BYTES}-byte limit.")
        try:
            return raw.decode("utf-8-sig")   # a leading BOM is tolerated
        except UnicodeDecodeError:
            raise RuleViolation("bad_encoding",
                                "File is not valid UTF-8 text.") from None

    # ----------------------------------------------------------------- guards
    def _dirty(self) -> bool:
        if self._draft is None:
            return False
        return self._draft != (self._source.text if self._source else "")

    def _require_idle(self) -> None:
        if self._busy is not None:
            raise RuleViolation(
                "busy", f"{self._busy.value} is still running; please wait.")

    def _require_replaceable(self) -> None:
        self._require_idle()
        if self._dirty():
            raise RuleViolation(
                "unapplied_edits",
                "There are unapplied edits. Apply or discard them first.")

    def _availability(self) -> dict[Operation, Availability]:
        out: dict[Operation, Availability] = {}
        for op in OPERATION_ORDER:
            if self._busy is not None:
                out[op] = Availability(False, "Another operation is running.")
            elif self._dirty():
                out[op] = Availability(
                    False, "Apply or discard your edits first.")
            elif op is Operation.EXECUTE:
                ok = (self._artifact is not None
                      and self._artifact.revision == self._revision)
                out[op] = Availability(
                    ok, "" if ok else
                    "No generated code is available for this revision.")
            elif self._source is None:
                out[op] = Availability(False, "Load or enter source first.")
            else:
                out[op] = Availability(True)
        return out

    # --------------------------------------------------------- source changes
    def _new_revision(self, name: str, text: str) -> None:
        self._revision += 1
        self._source = Source(name, text, self._revision)
        self._draft = None
        self._draft_name = None
        self._results = []
        self._artifact = None

    def load_text(self, name: str, text: str) -> None:
        """Replace the applied source (canned example or decoded upload)."""
        with self._lock:
            self._require_replaceable()
            self.validate_text(text)
            self._new_revision(name, text)
            self._epoch += 1

    def load_upload(self, name: str, raw: bytes) -> None:
        with self._lock:
            self._require_replaceable()
            self.load_text(name, self.decode_upload(raw))

    def begin_manual(self) -> None:
        """Open a blank editor; the applied source stays until Apply."""
        with self._lock:
            self._require_replaceable()
            self._draft = ""
            self._draft_name = "Manual input"
            self._epoch += 1

    def set_draft(self, text: str) -> None:
        with self._lock:
            self._require_idle()
            self._draft = text

    def apply(self, text: str | None = None) -> None:
        """Turn the draft (or ``text``) into a new applied revision."""
        with self._lock:
            self._require_idle()
            if text is not None:
                self._draft = text
            if self._draft is None or not self._dirty():
                raise RuleViolation("no_changes", "There are no changes to apply.")
            self.validate_text(self._draft)   # rejected: draft is kept
            name = self._draft_name or (
                self._source.name if self._source else "Manual input")
            self._new_revision(name, self._draft)

    def discard(self) -> None:
        with self._lock:
            self._require_idle()
            if self._draft is not None:
                self._draft = None
                self._draft_name = None
                self._epoch += 1

    # ------------------------------------------------------------- operations
    def begin(self, operation: Operation) -> Ticket:
        """Reserve the model for one operation (marks it busy)."""
        with self._lock:
            self._require_idle()
            if self._dirty():
                raise RuleViolation(
                    "unapplied_edits",
                    "There are unapplied edits. Apply or discard them first.")
            if self._source is None:
                raise RuleViolation("no_source",
                                    "Load or enter source first.")
            if operation is Operation.EXECUTE:
                art = self._artifact
                if art is None or art.revision != self._revision:
                    raise RuleViolation(
                        "not_available",
                        "No generated code is available for this revision.")
                ticket = Ticket(operation, artifact=art)
            else:
                ticket = Ticket(operation, source=self._source)
            self._busy = operation
            return ticket

    def finish(self, ticket: Ticket, result: Result) -> None:
        """Record the result of ``ticket`` and release the busy state."""
        with self._lock:
            self._busy = None
            if ticket.revision != self._revision:
                return                      # stale result: never shown
            self._results.insert(0, result)
            del self._results[MAX_RESULTS:]
            if ticket.operation is Operation.COMPILE:
                art = result.artifact
                good = (result.outcome is Outcome.SUCCESS and art is not None
                        and art.revision == self._revision)
                self._artifact = art if good else None   # failed => invalidated

    # --------------------------------------------------------------- snapshot
    def snapshot(self) -> ModelState:
        with self._lock:
            applied = self._source.text if self._source else ""
            return ModelState(
                source=self._source,
                revision=self._revision,
                draft=self._draft,
                draft_name=self._draft_name,
                dirty=self._dirty(),
                busy=self._busy,
                editor_text=self._draft if self._draft is not None else applied,
                editor_epoch=self._epoch,
                results=tuple(self._results),
                artifact=self._artifact,
                availability=MappingProxyType(self._availability()),
            )
