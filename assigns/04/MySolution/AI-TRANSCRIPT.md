# AI-TRANSCRIPT.md

## Tool

Claude (Anthropic), run as a coding agent (Claude Code, model Sonnet 5.5) with file, shell and
browser-automation access in a Linux sandbox. It wrote all the code and documents in this folder.

## Prompts

* My prompt (verbatim): "do these assignments", with `Assign04.md` and `lambda1.py` attached.
  No further instructions were given for this assignment; every design choice below was made by
  the AI from the assignment text and may be revised by me.

## What the AI did (significant suggestions)

* Chose Flask and a package layout with `contract` / `model` / `controller` / `view` / `web` /
  `backend` (+ `reader`, `worker`), and the rule that the **controller** coordinates backend calls
  while the model is a passive state machine (`begin` / `finish`); wrote the reasoning in
  `ARCHITECTURE.md`.
* Chose to run Lint and Interpret in a **worker subprocess with a timeout** so a nonterminating
  program can be killed (threads cannot be killed).
* Wrote the restricted constructor reader on top of `ast` (no `eval`/`exec`).
* Kept the unapplied draft in the model so "no actions while edits are unapplied" is enforced
  server-side, not only by disabled buttons.
* Wrote 78 unit/integration tests, an import-graph architecture test, and a Playwright browser
  smoke test (32 checks); wrote the documents, including the reflection in `README.md`.

## Corrections and problems found while reviewing (by running things)

* `python3` in the sandbox was 3.11, which cannot import `lambda1.py` (`type` statements); a
  3.12 virtual environment was created and used for everything.
* Two test failures on the first full run were mistakes in the AI's own tests/text: an argument
  evaluated before the action it depended on, and Execute help text that did not say "generated
  code" as F7 requires (text changed).
* The first browser run found a **real UI bug**: a stale success notice overwrote the "could not
  reach the local server" error (`static/app.js`); fixed. It also exposed a race in the test's wait
  condition (B10); fixed. The browser test needed a Chromium path override and `bypass_csp` in the
  harness (explained in `TESTING.md`).
* Playwright's bundled browser build did not match the sandbox's installed Chromium; the test now
  accepts `CHROMIUM_PATH`.

## How the output was reviewed and tested

* Ran `python -m unittest discover -s tests -t .` (78 tests, all pass) and
  `python tests/browser_smoke.py` (32 checks, all pass); results are in `TESTING.md`.
* Ran the same commands from a clean copy of the folder with a fresh virtual environment
  (`pip install -r requirements-dev.txt`), started the server, checked with `curl` that the page and
  a factorial interpretation work, and checked from `/proc/net/tcp` that the server listens only on
  127.0.0.1.
* Viewed a screenshot of the initial page. Did **not** view screenshots of the other states,
  test in Firefox/Safari, or test on Windows/macOS.
* Re-derived the demonstration outputs in `README.md` from the real browser run (B6, B9, B11,
  B14–B17, B22, B23), not from expectation.
* Not independently reviewed by a second person. **Before submitting I should read the code and
  documents, run the commands in `README.md` myself, and edit this file so it states what I
  personally checked and changed.**
