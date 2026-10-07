"""Model tests: no browser, no web server, no backend."""
import unittest

from lambda_ui.contract import Artifact, Operation, Outcome, Result
from lambda_ui.model import MAX_SOURCE_BYTES, AppModel, RuleViolation


def ok_result(ticket, outcome=Outcome.SUCCESS, artifact=None):
    return Result(ticket.operation, ticket.revision, outcome, "m", artifact)


class SourceEntry(unittest.TestCase):
    def test_manual_input_without_upload(self):
        m = AppModel()
        m.begin_manual()
        s = m.snapshot()
        self.assertEqual((s.editor_text, s.dirty, s.source), ("", False, None))
        m.apply("D0Eint(1)")
        s = m.snapshot()
        self.assertEqual((s.source.name, s.source.text, s.revision),
                         ("Manual input", "D0Eint(1)", 1))
        self.assertFalse(s.dirty)

    def test_edit_and_apply_creates_new_revision(self):
        m = AppModel()
        m.load_text("Example", "D0Eint(1)")
        m.set_draft("D0Eint(2)")
        self.assertTrue(m.snapshot().dirty)
        m.apply()
        s = m.snapshot()
        self.assertEqual((s.source.text, s.source.name, s.revision), ("D0Eint(2)", "Example", 2))

    def test_replacement_creates_new_revision_and_clears_results(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        t = m.begin(Operation.LINT); m.finish(t, ok_result(t))
        self.assertEqual(len(m.snapshot().results), 1)
        m.load_text("B", "D0Eint(2)")
        s = m.snapshot()
        self.assertEqual((s.revision, s.results, s.source.name), (2, (), "B"))

    def test_rejected_changes_keep_previous_source_and_draft(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        for bad in ["", "   \n\t ", "x" * (MAX_SOURCE_BYTES + 1)]:
            with self.assertRaises(RuleViolation):
                m.apply(bad)
            s = m.snapshot()
            self.assertEqual((s.source.text, s.revision), ("D0Eint(1)", 1))
            self.assertEqual(s.draft, bad)           # rejected edit still available
        with self.assertRaises(RuleViolation):
            m.load_text("C", "  ")
        self.assertEqual(m.snapshot().source.name, "A")

    def test_upload_validation(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        for raw, code in [(b"\xff\xfe\x00bad", "bad_encoding"),
                          (b"  \n", "empty_source"),
                          (b"a" * (MAX_SOURCE_BYTES + 1), "too_large")]:
            with self.assertRaises(RuleViolation) as cm:
                m.load_upload("f.txt", raw)
            self.assertEqual(cm.exception.code, code)
            self.assertEqual(m.snapshot().revision, 1)
        m.load_upload("f.txt", "﻿D0Eint(5)".encode("utf-8"))   # BOM tolerated
        self.assertEqual(m.snapshot().source.text, "D0Eint(5)")

    def test_size_limit_counts_bytes(self):
        m = AppModel()
        with self.assertRaises(RuleViolation):
            m.load_text("big", "é" * (MAX_SOURCE_BYTES // 2 + 1))
        m.load_text("max", "a" * MAX_SOURCE_BYTES)

    def test_unapplied_edits_block_actions_and_replacement(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        m.set_draft("D0Eint(2)")
        for call in (lambda: m.begin(Operation.LINT),
                     lambda: m.load_text("B", "D0Eint(3)"),
                     lambda: m.load_upload("f", b"D0Eint(4)"),
                     m.begin_manual):
            with self.assertRaises(RuleViolation) as cm:
                call()
            self.assertEqual(cm.exception.code, "unapplied_edits")
        self.assertFalse(any(a.enabled for a in m.snapshot().availability.values()))
        m.discard()
        s = m.snapshot()
        self.assertEqual((s.dirty, s.editor_text), (False, "D0Eint(1)"))
        self.assertTrue(s.availability[Operation.LINT].enabled)

    def test_apply_without_changes_is_not_a_new_revision(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        with self.assertRaises(RuleViolation) as cm:
            m.apply("D0Eint(1)")
        self.assertEqual(cm.exception.code, "no_changes")
        self.assertEqual(m.snapshot().revision, 1)

    def test_manual_input_keeps_applied_source_until_apply(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        m.begin_manual()
        s = m.snapshot()
        self.assertEqual((s.editor_text, s.source.text, s.dirty), ("", "D0Eint(1)", True))
        m.discard()
        self.assertEqual(m.snapshot().editor_text, "D0Eint(1)")


class OperationRules(unittest.TestCase):
    def test_actions_need_applied_source(self):
        m = AppModel()
        with self.assertRaises(RuleViolation) as cm:
            m.begin(Operation.LINT)
        self.assertEqual(cm.exception.code, "no_source")
        self.assertFalse(any(a.enabled for a in m.snapshot().availability.values()))

    def test_busy_blocks_everything_until_finish(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        t = m.begin(Operation.INTERPRET)
        self.assertEqual(m.snapshot().busy, Operation.INTERPRET)
        for call in (lambda: m.begin(Operation.LINT), lambda: m.set_draft("x"),
                     lambda: m.apply("x"), lambda: m.load_text("B", "y"),
                     m.discard, m.begin_manual):
            with self.assertRaises(RuleViolation) as cm:
                call()
            self.assertEqual(cm.exception.code, "busy")
        m.finish(t, ok_result(t))
        s = m.snapshot()
        self.assertIsNone(s.busy)
        self.assertEqual(s.results[0].operation, Operation.INTERPRET)
        m.begin(Operation.LINT)      # allowed again

    def test_execute_requires_artifact_for_current_revision(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        self.assertFalse(m.snapshot().availability[Operation.EXECUTE].enabled)
        with self.assertRaises(RuleViolation) as cm:
            m.begin(Operation.EXECUTE)
        self.assertEqual(cm.exception.code, "not_available")
        t = m.begin(Operation.COMPILE)
        m.finish(t, ok_result(t, artifact=Artifact(1, "py", "code")))
        self.assertTrue(m.snapshot().availability[Operation.EXECUTE].enabled)
        te = m.begin(Operation.EXECUTE)
        self.assertEqual(te.artifact.payload, "code")
        m.finish(te, ok_result(te))
        # new revision invalidates the artifact
        m.load_text("B", "D0Eint(2)")
        self.assertIsNone(m.snapshot().artifact)
        self.assertFalse(m.snapshot().availability[Operation.EXECUTE].enabled)

    def test_failed_or_mismatched_recompile_invalidates_artifact(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        t = m.begin(Operation.COMPILE)
        m.finish(t, ok_result(t, artifact=Artifact(1, "py", "code")))
        t = m.begin(Operation.COMPILE)
        m.finish(t, ok_result(t, outcome=Outcome.RUNTIME_ERROR))
        self.assertIsNone(m.snapshot().artifact)
        t = m.begin(Operation.COMPILE)
        m.finish(t, ok_result(t, artifact=Artifact(99, "py", "stale")))   # wrong revision
        self.assertIsNone(m.snapshot().artifact)

    def test_non_compile_results_never_install_artifacts(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        t = m.begin(Operation.LINT)
        m.finish(t, ok_result(t, artifact=Artifact(1, "py", "sneaky")))
        self.assertIsNone(m.snapshot().artifact)

    def test_stale_result_is_dropped(self):
        m = AppModel()
        m.load_text("A", "D0Eint(1)")
        t = m.begin(Operation.LINT)
        m._revision += 1            # simulate a revision change under a running op
        m.finish(t, ok_result(t))
        self.assertEqual(m.snapshot().results, ())
        self.assertIsNone(m.snapshot().busy)


if __name__ == "__main__":
    unittest.main()
