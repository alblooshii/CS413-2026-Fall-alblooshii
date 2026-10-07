"""HTTP layer through Flask's test client, with the real backend."""
import io
import json
import unittest

from lambda_ui import __main__ as entry
from lambda_ui.web import create_app


class Web(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def post(self, url, body=None):
        r = self.client.post(url, json=body)
        return r.status_code, r.get_json()

    def test_index_and_headers(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("script-src 'self'", r.headers["Content-Security-Policy"])
        html = r.get_data(as_text=True)
        for label in ("Choose File", "Manual input", "Factorial (canned)", "Fibonacci (canned)"):
            self.assertIn(label, html)
        self.assertNotIn("<script>", html.replace('<script src', ''))   # no inline script

    def test_loopback_only(self):
        self.assertEqual(entry.HOST, "127.0.0.1")

    def test_factorial_end_to_end(self):
        st, vm = self.post("/api/load/canned", {"key": "factorial"})
        self.assertEqual(st, 200)
        self.assertEqual(vm["source_label"], "Factorial (canned) — revision 1")
        st, vm = self.post("/api/action/interpret")
        self.assertEqual(vm["results"][0]["message"], "D0Vint(arg1=3628800)")
        self.assertEqual(vm["results"][0]["title"],
                         "Interpret · revision 1 · ✔ Success")
        self.assertEqual([a["label"] for a in vm["actions"]],
                         ["Lint", "Interpret", "Type-check", "Compile", "Execute"])
        self.assertFalse(vm["actions"][4]["enabled"])

    def test_open_expression_flow(self):
        self.post("/api/load/manual")
        st, vm = self.post("/api/apply", {"text": 'D0Evar("x")'})
        self.assertEqual(vm["source_label"], "Manual input — revision 1")
        st, vm = self.post("/api/action/lint")
        self.assertEqual(vm["results"][0]["message"], "Undeclared variable(s): x")
        self.assertIn("Language error", vm["results"][0]["outcome_label"])

    def test_rejections_are_409_and_preserve_state(self):
        self.post("/api/load/canned", {"key": "fibonacci"})
        st, vm = self.post("/api/apply", {"text": "   "})
        self.assertEqual(st, 409)
        self.assertEqual(vm["applied_text"].splitlines()[0][:9], "# Fibonac")
        self.assertFalse(vm["notice"]["ok"])
        # dirty draft blocks actions
        self.client.put("/api/draft", json={"text": "D0Eint(1)"})
        st, vm = self.post("/api/action/lint")
        self.assertEqual(st, 409)
        self.assertTrue(vm["dirty"])
        st, vm = self.post("/api/discard")
        self.assertEqual(st, 200)
        self.assertFalse(vm["dirty"])

    def test_upload_valid_invalid_and_oversize(self):
        def up(data, name="p.txt"):
            r = self.client.post("/api/load/file",
                                 data={"file": (io.BytesIO(data), name)},
                                 content_type="multipart/form-data")
            return r.status_code, r.get_json()
        st, vm = up(b'D0Eop2("+", D0Eint(20), D0Eint(22))')
        self.assertEqual((st, vm["source_label"]), (200, "p.txt — revision 1"))
        st, vm = up(b"\xff\xfe\x00")
        self.assertEqual(st, 409)
        self.assertIn("UTF-8", vm["notice"]["message"])
        self.assertEqual(vm["revision"], 1)
        st, vm = up(b"a" * 70000)
        self.assertEqual(st, 409)
        self.assertEqual(vm["revision"], 1)
        st, vm = up(b"a" * 300000)           # beyond the HTTP body cap
        self.assertEqual(st, 409)
        self.assertEqual(vm["revision"], 1)

    def test_html_like_text_passes_through_unmodified(self):
        self.post("/api/load/manual")
        text = 'D0Evar("<b>x</b>&amp;")'
        self.post("/api/apply", {"text": text})
        vm = self.post("/api/action/lint")[1]
        self.assertEqual(vm["results"][0]["message"], "Undeclared variable(s): <b>x</b>&amp;")
        self.assertEqual(vm["editor_text"], text)


if __name__ == "__main__":
    unittest.main()
