# E12 — Migrate verified legacy destinations

Acceptance: host
Requires: E11

## Purpose and delivery

Implement and execute the finite verified migration from E11 under the
[master](../Export-Execution-Plan.md) and
[compatibility design](../Export-Design.md#compatibility-and-migration). Read
the delivered inventory/generation APIs and complete protected queue transition,
historical recovery, document rewrite and controller restart paths.

Use E11's inventory as the finite worklist and E09's
`preview_document_links`/`apply_document_links` for ordinary destination changes,
under the [remaining delivery boundaries](../Export-Design.md#remaining-delivery-boundaries).
Keep discovery/classification in E11 and severity in E10. Extend the existing
APIs only for an evidenced migration gap; no separate rewrite engine, migration
launcher or repository-wide transaction is required.

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

Apply one document atomically. On interruption, reread and revalidate the finite
worklist: already verified replacements are no-ops, unchanged pending edits can
resume, and changed inputs remain pending. Keep protected recovery in its existing
transaction. Update E11's dispositions with applied, conflicting, unavailable or
externally pending outcomes so E13 need not rediscover the same references.

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
