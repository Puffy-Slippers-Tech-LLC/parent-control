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
driver or alter product acceptance. Both assigned families remain owned by
this row and share the existing capture/reference mechanics.
Retain `31c8c32c`'s partial snapshot/truncation and denied-reader behavior and
`41f23bfd`'s original-selector replay after a fully validated host checkpoint
mismatch. Malformed progress and VM/mixed selection mismatch retain their refusal;
do not introduce broader replay, checkpoint reset or new repair retries.

## Validation and close-out

Follow the master's [mandate boundaries](../Export-Execution-Plan.md#delivery).
Reuse shared capture/reference safety checks; add focused private checks for the
distinct repair and E2E consumer policies rather than copying the common matrix.
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

Retain repair diagnostics' 4-MiB total, 128-KiB/file and 64-file bounds with
bounded_tails, may_be_truncated, read_failures and limit_reached. Verification
never infers an unreported pass or crosses case/target/aggregate companions.
E2E formal failure, diagnosis and promotion keep distinct original identities;
retained acceptance and Git retries preserve their existing result/commit and
staging guards. Apply actual-file source guards at each specialized safe boundary.
