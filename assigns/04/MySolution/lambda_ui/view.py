"""View (server side): presentation of model state for the browser.

``present`` converts an immutable ``ModelState`` (plus the controller's last
``Notice``) into plain, display-ready data. It contains no language analysis
and no knowledge of how interpreters or compilers are invoked. The browser
half of the view is ``static/app.js`` and ``templates/index.html``.
"""
from __future__ import annotations

from .contract import OPERATION_ORDER, Operation, Outcome, Result
from .model import ModelState

ACTION_LABELS = {
    Operation.LINT: "Lint",
    Operation.INTERPRET: "Interpret",
    Operation.TYPECHECK: "Type-check",
    Operation.COMPILE: "Compile",
    Operation.EXECUTE: "Execute",
}

# Text (not colour alone) conveys status: a symbol plus a word.
OUTCOME_LABELS = {
    Outcome.SUCCESS: "✔ Success",
    Outcome.INPUT_ERROR: "✖ Input error",
    Outcome.LANGUAGE_ERROR: "✖ Language error",
    Outcome.RUNTIME_ERROR: "✖ Runtime error",
    Outcome.BACKEND_FAILURE: "⚠ Tool failure",
    Outcome.NOT_IMPLEMENTED: "ℹ Not implemented",
}

EXECUTE_HELP = ("Execute is for testing generated code produced by Compile. "
                "It is unavailable until compilation is implemented and has "
                "produced an artifact for the current revision.")


def _present_result(r: Result) -> dict:
    label = OUTCOME_LABELS[r.outcome]
    return {
        "action": ACTION_LABELS[r.operation],
        "revision": r.revision,
        "outcome": r.outcome.value,
        "outcome_label": label,
        "title": f"{ACTION_LABELS[r.operation]} · revision {r.revision} "
                 f"· {label}",
        "message": r.message,
    }


def present(state: ModelState, notice=None) -> dict:
    src = state.source
    if src is None:
        source_label = "No source applied yet"
    else:
        source_label = f"{src.name} — revision {src.revision}"
    if state.busy is not None:
        status = f"Busy: {ACTION_LABELS[state.busy]} is running…"
    elif state.dirty:
        status = ("Unapplied edits: press Apply changes or Discard changes "
                  "before running actions or loading other source.")
    elif src is None:
        status = "Ready. Load an example or choose Manual input."
    else:
        status = "Ready."
    actions = []
    for op in OPERATION_ORDER:
        a = state.availability[op]
        actions.append({"id": op.value, "label": ACTION_LABELS[op],
                        "enabled": a.enabled, "reason": a.reason})
    return {
        "source_label": source_label,
        "revision": state.revision,
        "applied_text": src.text if src else "",
        "editor_text": state.editor_text,
        "editor_epoch": state.editor_epoch,
        "dirty": state.dirty,
        "busy": state.busy.value if state.busy else None,
        "status": status,
        "actions": actions,
        "execute_help": EXECUTE_HELP,
        "results": [_present_result(r) for r in state.results],
        "notice": ({"ok": notice.ok, "message": notice.message}
                   if notice is not None else None),
    }
