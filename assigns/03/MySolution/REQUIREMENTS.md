# Requirements Specification
## A Web-Based Environment for Testing LAMBDA

Source: `LAMBDA-UI-informal-requirements.md` (instructor's stakeholder brief).

---

## 1. Purpose

Provide a browser-based environment where students and the instructor can
write, compile, and run short LAMBDA programs; inspect compiler output; and
keep named example programs as a repeatable, self-checking test collection.
The environment is a **client for a compiler**, not the compiler itself; the
compiler is a separate, still-evolving project developed by another team.

## 2. Stakeholders and Users

| Stakeholder | Goals |
| --- | --- |
| Course instructor | Demonstrate LAMBDA programs live in lecture; move between examples quickly; trust that student confusion is about their program, not the tool. Also the primary requirements source for this document. |
| Students writing LAMBDA programs | Write, run, and understand the result of a program with minimal setup; keep and return to their own work. |
| Students working on the compiler | Run a saved collection of example programs against the compiler to check whether a change broke anything. |

## 3. Scope

### 3.1 System boundary

The **testing environment** (this project) is a browser-based editor and
runner. The **compiler** (a separate, evolving project) accepts a program and
returns a compile result, a run result, or an error, and optionally an AST or
generated code. The environment depends on a defined interface to the
compiler but does not implement compilation itself, and must not assume a
specific compiler implementation.

### 3.2 In scope for version 1

- Single-user, local use on a student's or instructor's own machine.
- Writing, loading (from a file or from a built-in example), editing,
  compiling, and running one LAMBDA program at a time.
- Distinguishing compile-time from run-time outcomes, including errors.
- Named, saved test collections with expected outcomes, run as a batch.
- A defined, swappable interface to the compiler, usable with a mock/sample
  backend before the real compiler is ready.
- Keyboard operability and non-color-dependent status for core tasks.

### 3.3 Explicitly out of scope for version 1

- Public/hosted deployment, user accounts, or authentication.
- Multiple people editing the same program together in real time.
- Sharing a test collection across the class (the instructor states this is
  acceptable to omit from version 1).
- Development of the compiler itself.
- Exporting a program to a file (see Clarification Question 1) and any
  numeric-tolerance test comparison (see Question 2) — treated as future
  possibilities, not committed to for v1.

## 4. Clarification Questions and Assumptions

No stakeholder answers were available for this assignment. Each question
below states the assumption used to proceed, or is marked **Unresolved**
where an assumption seemed too risky to make silently.

| # | Question | Why it matters | Status / Assumption used |
| --- | --- | --- | --- |
| Q1 | Should a program be stored only in browser-local storage, or also exportable/importable as a file? | Determines whether persistence alone (FR-5) satisfies "return to it later," or file export is also required. | Unanswered. **Assumed**: browser-local persistence is sufficient for v1; import (FR-4) is required, export is deferred. |
| Q2 | Should test comparison use exact equality, or support approximate/tolerant matching (e.g., for non-integer results)? | Affects whether pass/fail can be determined unambiguously and automatically. | Unanswered. **Assumed**: exact equality on integers/Booleans, matching the brief's own examples. |
| Q3 | Should a long-running program be stopped automatically after a time limit, or only manually via a "Stop" action? | Affects whether the system needs a safety timeout for lecture use, beyond relying on the user noticing. | **Unresolved.** Not assumed — this is a real design/UX decision with lecture-time consequences, not just a wording gap. |
| Q4 | Is class-wide sharing of test collections fully out of scope for v1, or a stretch goal if time allows? | Determines whether any minimal sharing mechanism belongs on the v1 backlog at all. | Unanswered directly. **Assumed**: fully out of scope for v1, based on the instructor's stated willingness to live without it. |
| Q5 | Which specific browsers/versions count as "a browser students normally use"? | QR-4 needs a concrete, checkable target; "commonly used" alone can't be verified. | Unanswered. **Assumed**: current stable Chrome and Firefox on desktop. |
| Q6 | Should the AST/generated-code view be a structured/graphical display, or is a plain formatted text dump acceptable for v1? | Materially changes the size of FR-10; a tree-rendering UI is a much larger feature than a text panel. | Unanswered. **Assumed**: plain, readable text display is sufficient for v1; graphical rendering deferred. |
| Q7 | Should instructor-provided examples and a student's own saved tests be kept as visibly distinct categories in the UI? | Affects UI structure and interacts with the requirement to preserve unmodified originals (FR-3). | Unanswered. **Assumed**: yes, kept as two distinct, labeled categories. |
| Q8 | Once the LAMBDA source notation is finalized, must the environment also support entering a program directly as an AST (matching the current Python-based interpreter), or only the finalized text syntax? | The brief explicitly says the notation is unsettled; this affects the input model and the compiler-interface contract. | **Unresolved** — explicitly flagged as unsettled in the brief itself. Addressed structurally instead: FR-19 requires the compiler interface to be abstracted so either answer can be accommodated later without redesigning the UI. |

**Note:** Q3 and Q8 are left unresolved rather than assumed, because guessing
wrong on either has real consequences (lecture-time safety behavior, and a
fundamental input-format decision the brief itself says is still open). These
are the two points most worth raising with the instructor before
implementation starts.

## 5. Functional Requirements

Priority: **M**ust / **S**hould / **C**ould, relative to a usable version 1.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | The system shall let a user write or paste a LAMBDA program into an editable area. | M |
| FR-2 | The system shall provide a set of built-in example programs (including at least a factorial example) that a user can load into the editor. | M |
| FR-3 | When a user loads a built-in example, the system shall keep an unmodified copy of the original so the user can revert to it after editing. | M |
| FR-4 | The system shall let a user load a LAMBDA program from a local file into the editor without retyping it. | M |
| FR-5 | The system shall persist the user's current program and saved test collections across a page refresh and across sessions on the same machine, without requiring an account. | M |
| FR-6 | The system shall provide a "Compile" action that checks the program without executing it, and reports success or a compilation error. | M |
| FR-7 | The system shall provide a "Run" action that executes the program and reports its result or a runtime error. | M |
| FR-8 | The system shall present a compilation error and a runtime error in visibly and textually distinct ways, so the two are never mistaken for one another. | M |
| FR-9 | When the compiler reports a source location for an error, the system shall indicate the corresponding position in the editor. | M |
| FR-10 | The system shall provide an optional display of compiler-produced information (such as an AST or generated code) that is hidden by default and shown only on request. | S |
| FR-11 | The system shall let a user stop a running program before it completes. | M |
| FR-12 | The system shall remain responsive to editing and navigation while a compile or run operation is in progress. | M |
| FR-13 | If the program is edited while an earlier run for a previous version is still in progress, the system shall make clear which version of the program produced any result subsequently shown. | S |
| FR-14 | If the compiler cannot be reached, the system shall report this as an environment/connection problem distinct from a program error, and shall preserve the user's current program unchanged. | M |
| FR-15 | The system shall let a user create a named test consisting of a program and an expected outcome: either an expected value/Boolean result, or an expectation that compilation fails. | M |
| FR-16 | The system shall let a user run an entire named test collection and produce a summary of how many tests passed and which failed. | M |
| FR-17 | For a failing test, the system shall provide enough detail (expected vs. actual result, or error message) to investigate the failure. | M |
| FR-18 | A failure or unexpected error in one test shall not prevent the remaining tests in the same collection from running and being reported. | M |
| FR-19 | The compiler interface shall be defined so a mock/sample backend can be substituted for the real compiler during development; any output from a mock backend shall be clearly labeled as sample data, not an actual compilation result. | M |
| FR-20 | The primary tasks (loading an example, compiling, running, stopping, switching between examples) shall be operable using the keyboard alone. | S |
| FR-21 | The system shall indicate status (success, error, running) using text or icons in addition to color. | S |

## 6. Quality Requirements

| ID | Requirement | Note |
| --- | --- | --- |
| QR-1 (Responsiveness) | The system shall visibly acknowledge a Compile or Run action (e.g., a "running" indicator) within 200 ms, independent of how long the compiler itself takes. | 200 ms is **our proposed target**, not stakeholder-specified. |
| QR-2 (Usability) | A first-time user with no prior compiler experience shall be able to load an example and successfully run it within about 5 minutes, using only in-page guidance. | The 5-minute figure is **our proposal**, offered as a checkable stand-in for "easy to get started." |
| QR-3 (Reliability) | If the compiler connection is lost and later restored, the system shall let the user retry compiling or running without reloading the page or losing the current program. | Extends FR-14 into an explicit recovery guarantee. |
| QR-4 (Compatibility) | The system shall run correctly in the current stable release of at least two major desktop browsers (assumed: Chrome and Firefox; see Q5). | Concrete stand-in for "a browser students normally use." |
| QR-5 (Setup reproducibility) | A person following the provided setup instructions on a machine meeting the stated prerequisites shall be able to get the environment running locally with no undocumented steps. | Checkable via a documented setup walkthrough. |

## 7. External Interfaces and Dependencies

- **Compiler interface** (the environment's only required external
  dependency): given a program, returns either (a) a compile-only result
  (success or structured error, optionally with source location), (b) a run
  result (value/output or runtime error), or (c) supplementary information
  (AST / generated code) when available. The interface must be stable across
  a swap from a mock/sample backend to the real compiler (FR-19), since the
  compiler's own source notation and internals are still unsettled (Q8).
- **Local persistence**: browser-local storage for the current program and
  test collections (FR-5); no server-side database in v1.
- **Local file access**: reading a user-selected file to import a program
  (FR-4). File export is not required for v1 (Q1).
- **Browser environment**: a modern desktop browser (QR-4); no server
  deployment or hosting infrastructure required for v1.

## 8. Acceptance Criteria

| ID | Requirement | Preconditions | Action | Expected Result |
| --- | --- | --- | --- | --- |
| AC-1 | FR-6 | A syntactically valid program is in the editor. | Click "Compile." | System reports compilation success; no run result is shown. |
| AC-2 (failure) | FR-8 | A program with a syntax error is in the editor. | Click "Compile." | System shows a message clearly labeled as a compilation error; the system does not attempt to run the program. |
| AC-3 (failure) | FR-8 | A program that compiles successfully but fails during execution is in the editor. | Click "Run." | System shows a message clearly labeled as a runtime error, visibly distinct in labeling/styling from a compilation error. |
| AC-4 | FR-11, FR-12 | A program that does not terminate (e.g., unbounded recursion) is running. | Click "Stop." | Execution halts within a short, bounded time; the editor remains editable throughout and immediately after. |
| AC-5 (failure) | FR-14 | The compiler backend is unreachable (simulated). | Click "Compile" or "Run." | System shows a message clearly labeled as a connection/environment problem, not a program error; the program text in the editor is unchanged. |
| AC-6 (failure) | FR-18 | A test collection has 3 tests; one triggers an unexpected internal error when run. | Run the collection. | The summary reports a result for all 3 tests (2 resolved normally, 1 marked as errored); the run completes rather than stopping partway. |
| AC-7 | FR-3 | The "factorial" example has been loaded and then edited in the editor. | Reload/reset the example. | The editor shows the original, unmodified factorial example text, not the edited version. |
| AC-8 | FR-13 | A run is started on version A of a program and is still in progress. | Edit the program to version B before A's run finishes, then let A's result return. | The displayed result is labeled as belonging to version A, not presented as the result of the current (version B) editor content. |

## 9. Traceability

| Requirement | Source in brief / basis |
| --- | --- |
| FR-1 | "Trying a program": "typing or pasting a short program." |
| FR-2 | "Trying a program": "Having a few examples to start from would help... select a factorial example." |
| FR-3 | "Trying a program": "Students should be able to modify an example without losing access to the original." |
| FR-4 | "Trying a program": "Students may already have programs saved in files, and they should not have to retype them." |
| FR-5 | "Trying a program" / "Keeping examples as tests": "keep a program... and return to it later"; "I would be frustrated if refreshing the page meant losing the examples." |
| FR-6 | "Trying a program": "Sometimes I only want to check whether a program compiles." |
| FR-7 | "Trying a program": "At other times, I want to run it and see the answer." |
| FR-8 | "Understanding what happened": "A compilation error and a failure while running the program should not look like the same thing." |
| FR-9 | "Understanding what happened": "the environment should help the student find that place in the source." |
| FR-10 | "Trying a program": "inspect information the compiler produces, such as an abstract syntax tree or generated code... I do not want all of that detail to get in the way." |
| FR-11 | "Understanding what happened": "There should be a way to stop it and move on." |
| FR-12 | "Understanding what happened": "The page should remain usable while work is in progress." |
| FR-13 | "Understanding what happened": "I need to know which version produced the result I am seeing." |
| FR-14 | "Understanding what happened": "I do not want students to think their program is wrong... keep their work and try again." |
| FR-15 | "Keeping examples as tests": "a collection of named tests. Each test would contain a program and some record of what should happen." |
| FR-16 | "Keeping examples as tests": "a quick summary of which tests worked as expected." |
| FR-17 | "Keeping examples as tests": "enough detail to investigate the ones that did not." |
| FR-18 | "Keeping examples as tests": "One troublesome test should not make the rest of the collection useless." |
| FR-19 | "The compiler is still evolving" (entire section). |
| FR-20 | "Keeping the project manageable": "Students should be able to perform the main tasks with a keyboard." |
| FR-21 | "Keeping the project manageable": "messages should make sense without depending only on colors." |
| QR-1 | "Keeping the project manageable": "respond promptly to ordinary actions" + assumption (200 ms figure). |
| QR-2 | Overview: "easy to get started" + assumption (5-minute figure). |
| QR-3 | Derived from FR-14 + "Understanding what happened" section. |
| QR-4 | "Keeping the project manageable": "a browser students normally use" + assumption (Q5). |
| QR-5 | "Keeping the project manageable": "another person can follow the instructions and get it running." |

## 10. Review Notes

Issues found while drafting this specification, and how they were addressed:

1. **Invented requirement not supported by the brief.** An early draft
   included "export the program to a file" as a Must requirement. The brief
   only asks for *importing* existing files, not exporting. Removed as a
   numbered requirement; recorded instead as Clarification Question 1 and
   left out of v1 scope, to avoid presenting an assumption as if it were a
   stated need.
2. **Non-testable combined requirement.** An early draft merged
   compile-only and run into one requirement ("the system shall check or
   execute a program"), which a single test couldn't unambiguously verify.
   Split into FR-6 and FR-7, each independently checkable (see AC-1/AC-2 vs
   AC-3).
3. **Vague term without a target.** The responsiveness requirement
   originally used "fast" with no way to check it. Replaced with QR-1's
   concrete (though proposed, not stakeholder-confirmed) acknowledgment-time
   target, explicitly flagged as our proposal.
4. **Requirement count above the suggested range.** The functional
   requirement count (21) slightly exceeds the suggested 12–20. This is
   because FR-20 (keyboard operability) and FR-21 (non-color status) were
   kept as two separate requirements rather than merged into one
   accessibility requirement — merging them would have produced a
   requirement that a single acceptance check couldn't cleanly verify.
   Documented here rather than forced to fit a count.
