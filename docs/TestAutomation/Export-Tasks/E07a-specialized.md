# E07a — Integrate repair and E2E launcher consumers

Acceptance: host
Requires: E07

## Purpose and delivery

Integrate the specialized launcher consumers assigned by E01 under the
[master](../Export-Execution-Plan.md) and
[compatibility design](../Export-Design.md#compatibility-and-migration). Read
complete `repair_evidence.py`, `fix-tests` repair/result handoffs, `write-e2e`
acceptance/continuation/close-out consumers and shared nested-owner cleanup.

Consume structured exact evidence and use the shared capture/reference APIs;
retain versioned legacy handoffs. Keep bounded diagnostic tails explicitly
partial: repair summaries or snapshots cannot replace required full proof.
Preserve original failures, passing applicability, specialized session/model
budgets, queue/target guards and cleanup ownership through retries, interruptions
and continuation. Do not migrate the specialized state machines into the ordinary
driver or alter product acceptance. Split independent families before this row
if the frozen inventory exceeds the complete validation envelope.
Retain `31c8c32c`'s partial snapshot/truncation and denied-reader behavior and
`41f23bfd`'s original-selector replay after a fully validated host checkpoint
mismatch. Malformed progress and VM/mixed selection mismatch retain their refusal;
do not introduce broader replay, checkpoint reset or new repair retries.

## Validation and close-out

Use private repair/E2E launcher fixtures for rotated raw reports, failed and
passing attempts, interrupted capture, missing member, denied helper, legacy
handoff and restarted continuation. Assert no synthetic pass, skipped selector,
or acceptance credit from truncated diagnostic tails. Retain the existing
failure-context rotation/denial regressions and
`test_repair_replays_original_selection_after_another_run_replaces_checkpoint`,
`test_repair_does_not_reset_an_invalid_checkpoint` and
`test_vm_repair_does_not_reset_checkpoints_after_selection_mismatch` as applicable.
Assert no extra session credit or weakened cleanup. No model sessions, live VM,
product suite or real remote operations. Run affected maintained launcher/evidence host
selections and safety checks, update their existing owners and follow the
master's cleanup and close-out.

## Frozen prerequisite insertion

E01b allocation: 120–165 min total; this consumer retains 30–45 min for cross-family
compatibility and all original acceptance. Repair and E2E state machines are
independent delivery owners, sharing only the frozen capture/reference mechanics.

When E07a is selected, before implementation insert exactly this contiguous block
immediately before it, with the existing briefs:

Brief navigation: [E07ap-repair](E07ap-repair.md), [E07ap-e2e](E07ap-e2e.md).
The literal rows below use queue-relative destinations; copy them unchanged.

```markdown
| Done | ID | Task | Requires | Scope | Estimate |
| --- | --- | --- | --- | --- | --- |
| [ ] | E07ap-repair | [Integrate repair evidence consumers](Export-Tasks/E07ap-repair.md) | E07 | Integrate exact repair proof and partial diagnostic handoffs while preserving original selectors, refusals and specialized policies | 45–60 min |
| [ ] | E07ap-e2e | [Integrate specialized E2E evidence consumers](Export-Tasks/E07ap-e2e.md) | E07ap-repair | Integrate exact E2E proof through formal failure, continuation, promotion and recovery without changing acceptance or budgets | 45–60 min |
```

Exact E07a Requires before: `E07`; after: `E07, E07ap-e2e`.
At insertion update this brief's top-level Requires to that same after field.
New briefs declare `Acceptance: host`, no Targets. Preserve every assertion above,
original Scope and acceptance and all other rows under the
[shared insertion route](../../Execution-Plans.md#execution-and-delegation) and
[frozen guards](../Export-Design.md#frozen-insertion-guard-review).
Finish owned cleanup, point to E07ap-repair and return `prerequisite_required`
or valid `continue` with the retained consumer handoff. Never execute prerequisites
or change checkpoints in that insertion session. After resumption check both
families' legacy/structured compatibility, exact proof and unchanged failure,
selector, promotion, session and cleanup policies before E07a can close.
