"""Automated browser smoke test (Playwright + Chromium). Not part of unittest.

Run:  python tests/browser_smoke.py      (needs `pip install -r requirements-dev.txt`
and a Playwright browser; see README). Prints one PASS/FAIL line per check with
the observed value, and exits non-zero if any check fails.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check(cid: str, features: str, desc: str, ok: bool, observed) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} ({features}) {desc} -- observed: {observed!r}")
    if not ok:
        FAILS.append(cid)


def main() -> int:
    port = free_port()
    env = dict(os.environ, LAMBDA_UI_TIMEOUT="3")
    server = subprocess.Popen([sys.executable, "-m", "lambda_ui", "--port", str(port)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/"
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1).read()
            break
        except OSError:
            time.sleep(0.2)
    try:
        with sync_playwright() as pw:
            # CHROMIUM_PATH lets you point at an existing Chromium/Chrome binary.
            exe = os.environ.get("CHROMIUM_PATH")
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            # bypass_csp: only so Playwright's own wait_for_function (string eval)
            # works; the page's CSP header is asserted separately in tests/test_web.py.
            page = browser.new_context(bypass_csp=True).new_page()
            run_checks(page, url, server)
            browser.close()
    finally:
        server.terminate()
        server.wait(5)
    print("\nRESULT:", "ALL CHECKS PASSED" if not FAILS else f"FAILED: {FAILS}")
    return 1 if FAILS else 0


def run_checks(page, url, server) -> None:
    def text(sel): return page.locator(sel).inner_text().strip()
    def result_titles(): return page.locator("#results article h3").all_inner_texts()
    def result_bodies(): return page.locator("#results article pre").all_inner_texts()
    def disabled(sel): return page.locator(sel).is_disabled()
    def set_editor(value):
        page.fill("#editor", value)
        page.wait_for_timeout(450)      # let the draft sync (200 ms debounce) finish
    def click_and_wait(sel, expect_text=None):
        page.click(sel)
        page.wait_for_function("document.getElementById('status').textContent.indexOf('Busy') !== 0",
                               timeout=15000)

    page.goto(url)
    page.wait_for_selector("#actions button")

    # S1 initial page -------------------------------------------------------
    labels = page.locator("#actions button").all_inner_texts()
    check("B1", "F4", "five action buttons in the required order",
          labels == ["Lint", "Interpret", "Type-check", "Compile", "Execute"], labels)
    menu = [page.locator(s).inner_text() for s in
            ("#load-file", "#load-manual", "#load-factorial", "#load-fibonacci")]
    check("B2", "F1", "Load source menu offers the four entries",
          menu == ["Choose File", "Manual input", "Factorial (canned)", "Fibonacci (canned)"], menu)
    check("B3", "F4", "all actions disabled before any source is applied",
          all(page.locator("#actions button").nth(i).is_disabled() for i in range(5)),
          [page.locator("#actions button").nth(i).is_disabled() for i in range(5)])
    page.screenshot(path=str(Path(tempfile.gettempdir()) / "lambda_ui_initial.png"))

    # S2 factorial ----------------------------------------------------------
    page.click("#load-factorial")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('Factorial')")
    check("B4", "F1,F8", "canned example shows name and revision",
          text("#source-label") == "Source: Factorial (canned) — revision 1", text("#source-label"))
    check("B5", "F1,F2", "canned example is loaded into the editable editor",
          "D0Efix" in page.input_value("#editor") and not page.locator("#editor").evaluate("e => e.readOnly"),
          page.input_value("#editor")[:30])
    click_and_wait("#action-interpret")
    check("B6", "F6,F9", "Interpret factorial(10) shows value with action/revision/outcome",
          result_bodies()[:1] == ["D0Vint(arg1=3628800)"] and
          result_titles()[:1] == ["Interpret · revision 1 · ✔ Success"],
          (result_titles()[:1], result_bodies()[:1]))

    # S3 edit / apply -------------------------------------------------------
    original = page.input_value("#editor")
    set_editor(original.replace("D0Eint(10))", "D0Eint(5))"))
    check("B7", "F2", "typing makes Apply/Discard available and disables actions and loading",
          not disabled("#apply") and not disabled("#discard") and disabled("#action-lint")
          and disabled("#load-fibonacci") and "Unapplied edits" in text("#status"),
          (disabled("#apply"), disabled("#action-lint"), text("#status")[:25]))
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 2')")
    check("B8", "F2,F8", "Apply creates revision 2 and clears earlier results",
          page.locator("#results article").count() == 0 and text("#no-results") != "",
          page.locator("#results article").count())
    click_and_wait("#action-interpret")
    check("B9", "F2,F6", "edited factorial(5) gives 120", result_bodies()[:1] == ["D0Vint(arg1=120)"], result_bodies()[:1])

    # S4 discard ------------------------------------------------------------
    applied = page.input_value("#editor")
    set_editor("garbage that should be discarded")
    page.click("#discard")
    page.wait_for_function("(a) => document.getElementById('editor').value === a", arg=applied)
    check("B10", "F2", "Discard restores the applied source",
          page.input_value("#editor") == applied and disabled("#apply"), page.input_value("#editor")[:20])

    # S5 fibonacci ----------------------------------------------------------
    page.click("#load-fibonacci")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('Fibonacci')")
    click_and_wait("#action-interpret")
    check("B11", "F1,F6", "Fibonacci(10) = 55", result_bodies()[:1] == ["D0Vint(arg1=55)"], result_bodies()[:1])

    # S6 manual input, open expression, lint -------------------------------
    page.click("#load-manual")
    page.wait_for_function("document.getElementById('editor').value === ''")
    check("B12", "F1,F2", "Manual input opens a blank editor and keeps the applied source for now",
          page.input_value("#editor") == "" and "Fibonacci" in text("#source-label"), text("#source-label"))
    set_editor('D0Evar("x")')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('Manual input')")
    check("B13", "F1,F8", "applied manual source named 'Manual input' with a new revision",
          text("#source-label") == "Source: Manual input — revision 4", text("#source-label"))
    click_and_wait("#action-lint")
    check("B14", "F5,F9", "Lint reports the undeclared variable as an error, in text",
          result_bodies()[0] == "Undeclared variable(s): x" and "Language error" in result_titles()[0],
          (result_titles()[0], result_bodies()[0]))
    set_editor('D0Elet("x", D0Eint(1), D0Evar("x"))')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 5')")
    click_and_wait("#action-lint")
    check("B15", "F5", "editing into a closed expression passes Lint",
          result_bodies()[0] == "No free variables found." and "Success" in result_titles()[0],
          (result_titles()[0], result_bodies()[0]))

    # S7 lint vs runtime failure -------------------------------------------
    set_editor('D0Eop2("/", D0Eint(1), D0Eint(0))')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 6')")
    click_and_wait("#action-lint")
    click_and_wait("#action-interpret")
    t, b = result_titles(), result_bodies()
    check("B16", "F5,F6", "closed program passes Lint but fails Interpret with a runtime error",
          "Success" in t[1] and "Runtime error" in t[0] and "ZeroDivisionError" in b[0], (t[:2], b[0]))
    set_editor('D0Eop2("+", D0Eint(1), D0Eint(2)')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 7')")
    click_and_wait("#action-interpret")
    check("B17", "F6", "malformed input is an Input error, distinct from Runtime error",
          "Input error" in result_titles()[0] and "Runtime error" not in result_titles()[0], result_titles()[0])

    # S8 rejection ----------------------------------------------------------
    before_label = text("#source-label")
    set_editor("   \n  ")
    page.click("#apply")
    page.wait_for_function("document.getElementById('notice').textContent.startsWith('Error')")
    check("B18", "F3", "whitespace-only source is rejected; previous source kept; rejected text stays in editor",
          "empty" in text("#notice").lower() and text("#source-label") == before_label
          and page.input_value("#editor") == "   \n  ", text("#notice"))
    page.click("#discard")
    page.wait_for_function("document.getElementById('editor').value.includes('D0Eop2')")
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.txt"
        bad.write_bytes(b"\xff\xfe\x00broken")
        page.set_input_files("#file-input", str(bad))
        page.wait_for_function("document.getElementById('notice').textContent.includes('UTF-8')")
        check("B19", "F1,F3", "invalid UTF-8 upload rejected; source unchanged",
              text("#source-label") == before_label, (text("#notice"), text("#source-label")))
        big = Path(td) / "big.txt"
        big.write_bytes(b"a" * 70000)
        page.set_input_files("#file-input", str(big))
        page.wait_for_function("document.getElementById('notice').textContent.includes('limit')")
        check("B20", "F3", "oversize upload rejected with the documented limit",
              "65536" in text("#notice") and text("#source-label") == before_label, text("#notice"))
        good = Path(td) / "sum.txt"
        good.write_text('D0Eop2("+", D0Eint(20), D0Eint(22))', encoding="utf-8")
        page.set_input_files("#file-input", str(good))
        page.wait_for_function("document.getElementById('source-label').textContent.includes('sum.txt')")
        click_and_wait("#action-interpret")
        check("B21", "F1,F6", "Choose File uploads a UTF-8 file, shows its name/revision, and it interprets to 42",
              result_bodies()[0] == "D0Vint(arg1=42)" and "sum.txt — revision 8" in text("#source-label"),
              (text("#source-label"), result_bodies()[0]))

    # S9 placeholders -------------------------------------------------------
    click_and_wait("#action-typecheck")
    click_and_wait("#action-compile")
    t, b = result_titles(), result_bodies()
    check("B22", "F7", "Type-check and Compile report 'not yet implemented', not success",
          "not yet implemented" in b[1] and "not yet implemented" in b[0]
          and "Not implemented" in t[0] and "Not implemented" in t[1] and "Success" not in t[0] + t[1],
          (t[:2], b[:2]))
    check("B23", "F4,F7", "Execute stays disabled and the page explains why",
          disabled("#action-execute") and "generated code" in text("#execute-help"), text("#execute-help"))

    # S10 literal rendering -------------------------------------------------
    set_editor('D0Evar("<b>bold</b><img src=x onerror=document.title=1>")')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 9')")
    click_and_wait("#action-lint")
    body = result_bodies()[0]
    check("B24", "F9", "HTML-like source/output is shown literally (no markup elements created, no script effect)",
          "<b>bold</b>" in body and page.locator("#results b, #results img, #editor b").count() == 0
          and page.title() == "LAMBDA Workbench", body)
    set_editor('D0Evar("a")\n')
    set_editor('# line1\n# line2\nD0Elet("x", D0Eint(1),\n    D0Evar("x"))')
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 10')")
    check("B25", "F9", "multi-line source with comments survives Apply with line breaks intact",
          page.input_value("#editor").count("\n") == 3, page.input_value("#editor"))

    # S11 keyboard ----------------------------------------------------------
    page.focus("#load-factorial")
    page.keyboard.press("Enter")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('Factorial')")
    page.focus("#action-interpret")
    page.keyboard.press("Space")
    page.wait_for_function("document.querySelectorAll('#results article').length > 0")
    check("B26", "keyboard", "load an example and run Interpret using only keyboard keys",
          result_bodies()[0] == "D0Vint(arg1=3628800)", result_bodies()[0])
    page.focus("#load-file")
    order = []
    for _ in range(12):
        page.keyboard.press("Tab")
        order.append(page.evaluate("document.activeElement.id || document.activeElement.tagName"))
    check("B27", "keyboard", "Tab reaches editor and the enabled action buttons in page order",
          "editor" in order and "action-lint" in order and order.index("action-lint") < order.index("action-interpret")
          if "action-interpret" in order else False, order)

    # S12 busy / timeout / retry -------------------------------------------
    slow = open(ROOT / "samples" / "fibonacci.txt", encoding="utf-8").read().replace("D0Eint(10))", "D0Eint(32))")
    page.click("#load-manual")
    page.wait_for_function("document.getElementById('editor').value === ''")
    set_editor(slow)
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 12')")
    page.click("#action-interpret")
    page.wait_for_function("document.getElementById('status').textContent.startsWith('Busy')")
    busy_state = {
        "status": text("#status"),
        "actions_disabled": all(page.locator("#actions button").nth(i).is_disabled() for i in range(5)),
        "editor_readonly": page.locator("#editor").evaluate("e => e.readOnly"),
        "load_disabled": disabled("#load-factorial"),
        "responsive": page.evaluate("1 + 1") == 2,
    }
    check("B28", "F10", "while a long run is in progress: busy status, controls disabled, page still responsive",
          busy_state["status"].startswith("Busy") and busy_state["actions_disabled"]
          and busy_state["editor_readonly"] and busy_state["load_disabled"] and busy_state["responsive"], busy_state)
    page.wait_for_function("document.getElementById('status').textContent.indexOf('Busy') !== 0", timeout=15000)
    check("B29", "F10", "the non-terminating/slow run is stopped by the timeout and reported as a tool failure",
          "Tool failure" in result_titles()[0] and "Timed out" in result_bodies()[0],
          (result_titles()[0], result_bodies()[0]))
    check("B30", "F10", "controls restored and source preserved after the failure",
          not disabled("#action-interpret") and page.input_value("#editor") == slow, text("#status"))
    # retry on a faster program
    set_editor(slow.replace("D0Eint(32))", "D0Eint(6))"))
    page.click("#apply")
    page.wait_for_function("document.getElementById('source-label').textContent.includes('revision 13')")
    click_and_wait("#action-interpret")
    check("B31", "F10", "after the failure a retry on a quick program succeeds (fib(6)=8)",
          result_bodies()[0] == "D0Vint(arg1=8)", result_bodies()[0])

    # S13 server unreachable -----------------------------------------------
    server.terminate(); server.wait(5)
    page.click("#action-lint")
    page.wait_for_function("document.getElementById('notice').textContent.includes('could not reach')", timeout=10000)
    check("B32", "F10", "when the server is unreachable the page says so and keeps the source",
          "could not reach" in text("#notice") and page.input_value("#editor") != "" and not disabled("#action-lint"),
          text("#notice")[:70])


if __name__ == "__main__":
    raise SystemExit(main())
