# SDD ledger — plan: docs/superpowers/plans/2026-10-07-landing.md

5 tasks. Spec: docs/superpowers/specs/2026-10-07-landing-design.md.
Execution: native inline, one fresh review at the end.

Verification model: no framework, no dependencies. `tools/verify.py` on
stdlib Python is the test suite for every task — it is the test, not a
companion to it. RED is "verify.py fails", GREEN is "verify.py passes".

## Pre-flight

Shared interfaces between tasks:

| Producer | Produces | Consumer | Status |
|---|---|---|---|
| Task 1 | `css/tokens.css`, `tools/verify.py` | Task 2 (style.css refs tokens), Task 3 (theme checks read it), Task 4 (meta checks) | ok |
| Task 1 | `tools/verify.py` CLI | every later task runs it | ok |
| Task 2 | `index.html`, `css/style.css` | Task 3 (theme script into head), Task 4 (meta into head) | ok |
| Task 4 | `static/*` | Task 5 (deploy serves repo root) | ok |

Tasks 1, 2 and 4 share nothing that can drift; 3 and 4 both edit `index.html`
but touch different regions (head script vs meta block) and each runs the
full verifier at its end.

Pre-flight rulings:

- **Plan Task 1 lists `css/tokens.css` before `tools/verify.py`.** That is
  production code before the test, which the TDD skill forbids outright, and
  the plan itself is wrong about it. Reversed for execution: the verifier is
  written first and watched fail on the absent `tokens.css`, which is a
  genuine failure and a meaningful RED. The commit is unchanged in content.
- **Plan Task 1 asks the verifier to flag dead tokens.** It cannot go GREEN
  that early: with no `style.css` and no `index.html` yet, every token is
  unused by definition. That check is written in Task 2, where consumers
  exist. Its absence in Task 1 is not a silent skip — the check lives in the
  same file from the first version, marked with the condition that enables it.