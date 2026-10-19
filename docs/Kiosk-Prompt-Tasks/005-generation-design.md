# 005 — Review retained-view admission proofs

Acceptance: review

Session boundary: review manager identity, concurrency, namespace and native
binding proofs using the reviewed [material/pin design](../SystemDesign/Kiosk-Confinement.md#planned-retained-material-and-immutable-pins)
and [activation/recovery boundary](../SystemDesign/Lifecycle.md#retained-material-activation-and-recovery).
Include its source-realization versus derived-invocation receipts. Preserve the
combined original scope. A source-storage redesign requires
a concrete proof gap and a bounded prerequisite rather than independent new work.

Read the [master](../Kiosk-Prompt.md), complete `prepare()`, `manager_generation()`,
generation verification/publication, native binding/staging detach and existing
`verify_updates()` / `system_native_update.stale_admission()` histories.

Design availability after unrelated sibling addition/removal or trust-kind change.
Required config, attested policy, native executable/library bytes, privilege helper
metadata and actually consumed runtime roots must still match. Removing layout
from a digest is insufficient: runtime placeholders no longer own the mounted
view after native staging detach. Specify where immutable pins live and how
their identity/lifetime is proven before reusing a manager's actual private view
or an equivalent safe source. Do not reconstruct it from vanished host siblings.

Document manager PID-reuse/thread/credential/label/namespace proofs, concurrent
exit/reexec/update handling, locks, source allowlists, publication interruption,
unknown/replaced ownership and required-drift refusal/reboot recovery. Use a finite
ambient-versus-required transition table and independent positive/negative
witnesses for 006/007. Keep enduring design in its confinement/lifecycle owners,
not a new competing protocol document. Review the proof and remaining risks before
implementation. This row supplies no host or installed pass for the new mechanism.
These proofs qualify the retained-view reuse change only. Reuse valid existing
confinement coverage; do not reopen the full offense/defense catalogue or redesign
unrelated session services to close this entry-availability defect.
