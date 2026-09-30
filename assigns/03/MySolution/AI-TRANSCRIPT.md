# AI-Assisted Work Transcript

## Tool used

Claude (Anthropic), used interactively in a chat/agent session to help draft
`REQUIREMENTS.md`.

## How it was used

1. I gave Claude the informal stakeholder brief
   (`LAMBDA-UI-informal-requirements.md`) and the assignment sheet
   (`Assign03.md`) and asked it to help turn the brief into a requirements
   specification following the assignment's structure (stakeholders/scope,
   clarification questions, functional/quality requirements, acceptance
   criteria, traceability, review notes).
2. Claude produced a full first draft of `REQUIREMENTS.md`, including a set
   of clarification questions with assumptions, ~21 functional requirements,
   5 quality requirements, 8 acceptance criteria, a traceability table, and
   self-identified review issues.
3. I reviewed the draft and pushed back on two specific points where I
   thought Claude had been too quick to resolve genuine ambiguity by
   assumption rather than flagging it as an open question:
   - **Stop behavior (Q3):** whether a stuck/long-running program should be
     stopped only manually (by the user clicking "Stop") or also
     auto-killed after a time limit. I decided this should be left
     **Unresolved** rather than assumed, since guessing wrong has real
     lecture-time consequences and no part of the brief hints at an answer.
   - **Requirement count / accessibility requirements:** whether FR-20
     (keyboard operability) and FR-21 (non-color status indication) should
     stay as two separate requirements (pushing the total slightly over the
     assignment's suggested 12–20) or be merged into one combined
     accessibility requirement to land inside the suggested range. I chose
     to **keep them separate**, since a merged requirement would cover two
     independently verifiable behaviors and would be harder to check with a
     single acceptance test — and the assignment explicitly says not to
     split or merge requirements merely to hit a count.
4. Claude incorporated both decisions into the final document (§4 records
   Q3 as Unresolved with a short rationale; §10 Review Note #4 records and
   justifies keeping FR-20/FR-21 separate and the resulting count of 21).
5. I read the full document end-to-end afterward to check for internal
   consistency (e.g., that every FR referenced in the traceability table and
   acceptance criteria actually exists, that priorities were reasonable, and
   that no requirement described an implementation choice rather than
   required behavior) and did not find further issues beyond the three
   already recorded in §10 of the document.

## Significant corrections made to the AI's output

- Rejected an invented "export program to a file" requirement that the
  brief did not support (see REQUIREMENTS.md §10, item 1).
- Required a compile-only vs. run requirement that had been merged into one
  non-testable requirement to be split into two independently verifiable
  ones (FR-6, FR-7; see §10, item 2).
- Replaced a vague "fast" performance requirement with an explicit,
  clearly-labeled proposed numeric target (QR-1; see §10, item 3).
- Directed that Q3 (stop behavior) be left unresolved rather than resolved
  by assumption, and that FR-20/FR-21 remain separate rather than merged
  purely to hit the suggested requirement count.

No requirements, assumptions, or stakeholder answers in the final document
are presented as confirmed by the instructor; all are labeled as either
drawn directly from the brief, an explicit assumption I made, or an
explicitly unresolved question, per the assignment's instructions.
