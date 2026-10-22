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
