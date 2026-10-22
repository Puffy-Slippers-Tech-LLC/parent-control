# E12 — Migrate verified legacy destinations

Acceptance: host
Requires: E11

## Purpose and delivery

Implement and execute the finite verified migration from E11 under the
[master](../Export-Execution-Plan.md) and
[compatibility design](../Export-Design.md#compatibility-and-migration). Read
the delivered inventory/generation APIs and complete protected queue transition,
historical recovery, document rewrite and controller restart paths.

Preview exact original document bytes, claim/context, old destination, verified
replacement member and dependency digests. Apply only unchanged owned inputs,
retaining labels, claims, task order/scope, completion and valid historical checks.
Migrate all inventoried exact recoverable references across declared consumer
families, not just the current queue. Respect preexisting dirty/staged work;
leave conflicting edits with a concrete disposition. Active/protected controller
changes go through their existing exact recovery transaction at a safe boundary;
never edit checkpoints or launch/stop another campaign. Record any pending
external application precisely rather than claiming it applied. Absent/ambiguous
proof stays for E13; do not select a plausible filename or rerun acceptance.

## Validation and close-out

Follow the master's [mandate boundaries](../Export-Execution-Plan.md#delivery).
Reuse shared publication, resolver and cleanup checks. Use private fixtures for
the migration's distinct preview/apply idempotence, changed document/candidate,
partial interruption, protected active/suspended history, legacy generation and
unrelated edits. Verify each applied reference resolves to identical original
proof and commands/cleanup after unrelated export rotation. Run registered
read-only post-migration inventory on real documents, scoped host tests and
changed Markdown checks. Keep finite pending/protected dispositions in the
existing owner and follow the master's cleanup and close-out.
