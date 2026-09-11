# Assignment 1: Eight-Queens Puzzle — ATS to Python Translation

This repository contains the original ATS implementation of the
Eight-Queens Puzzle (`eightqueens.dats`), an AI-assisted translation
of the program into Python 3 (`eightqueens.py`), and a test suite
(`tests/test_eightqueens.py`) verifying the translation's correctness.

## Files

- `eightqueens.dats` — original ATS source program
- `eightqueens.py` — Python 3 translation
- `tests/test_eightqueens.py` — test suite
- `AI-TRANSCRIPT.md` — record of the AI-assisted translation process

## AI Reflection

I used Claude (Anthropic) to translate the original ATS Eight-Queens
program into Python 3. The AI did well at understanding the structure
of the ATS code and mapping most of it directly onto Python: the tuple
based board representation, the printing helpers, and the safety-check
logic all translated cleanly and correctly on the first attempt.

However, the initial translation had a serious hidden bug: it
translated the `search` function's recursion literally, which crashed
with a `RecursionError`. The root problem was a language-semantics
difference the AI initially missed: the original ATS source explicitly
states that `search` is tail-recursive, and ATS's compiler optimizes
tail calls into a loop with constant stack space. Python has no such
optimization, so the same recursive structure that runs fine in ATS
overflows Python's call stack. This was not a syntax error I could
have caught by just reading the code quickly; I had to understand what
tail-call optimization actually does at the compiler level to see why
a "correct-looking" translation would still fail at runtime.

I would not have trusted this translation without testing it. The
code looked reasonable and even ran for small inputs, but it silently
failed to produce a full result at the actual puzzle size (N=8). Only
running it and reading the resulting stack trace exposed the problem.

Once I flagged the crash, the AI correctly diagnosed the cause and
rewrote the function as an explicit loop, which I then verified myself
by comparing its output, board-for-board, against the exact solutions
documented in the original ATS source, and by writing and running an
independent test suite.

Overall, AI sped up the mechanical part of translation significantly,
but it did not reduce the amount of verification work required — if
anything, it shifted my effort from writing code to critically
reading, testing, and reasoning about *why* the generated code
behaved the way it did.
