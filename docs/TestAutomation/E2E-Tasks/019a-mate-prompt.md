# 019a — Inspect and qualify the kiosk MATE prompt entry

Estimate: 35–55 minutes; an estimate, never a stop timer. Follow the
[master execution contract](../E2E-Execution-Plan.md#execute-one-task) and its
[provider rules](../E2E-Execution-Plan.md#external-provider-work-within-the-sequence).
This brief does not select or skip tasks.

## Scope and prerequisites

Deliver **MATE provider owner, real request context and guarded Cancel/form return**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **012a** — REQUEST04 duration; REQUEST05/06/08 and REQUEST09 invalid-input branch, kiosk.
- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **013** — REQUEST11/12 kiosk Cancel and Escape.

## Read only this context

Read AUTH01 and the MATE provider row, [the kiosk agent service](../../../data/systemd/user/oh-no-parent-control-polkit-agent.service), prompt methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py) and the existing request worker.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Enter the actual kiosk MATE Polkit challenge through one explicit owned Request action. Bind the agent owner, selected administrator, public child/duration/app context and protected field. Implement a guarded provider-local Cancel with independent form readback. Keep MATE separate from Shell Polkit. Missing displayed request context is an explicit unmet prerequisite; broker state cannot fill it.

## Live VM acceptance

In the guarded VM, read one real challenge, Cancel once, then independently observe disappearance and the usable unchanged form. Reenter independently and reject wrong agent/owner, ambiguous field and replacement prompt. Preserve choices and no-error result. No password submission. Require sanitized evidence and cleanup.

Implement and register this planned fixed qualification before invoking it:

```sh
tools/run-tests integration check_e2e_mate_prompt
```

Use the existing guarded envelope. Pass applicable cleanup-safety checks in
isolation before live execution; require independent valid entry, wrong-entry
refusal, sanitized evidence and owned cleanup. A new selector needs its
argument-free launcher and cleanup coverage. Host tests alone cannot close this row.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**019a** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
