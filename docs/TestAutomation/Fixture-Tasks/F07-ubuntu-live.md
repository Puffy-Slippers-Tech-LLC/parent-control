# F07 — Refresh an owned live Ubuntu VM

Acceptance: installed
Targets: onpc-Ubuntu26.04
Requires: F49

## Purpose and scope

Deliver [live diagnostic refresh](../Fixture-Design.md#live-refresh-and-recorded-attempts)
through the F01-reviewed `tools/test-vm` maintenance extension. Reuse F05/F06's
exact provisioning, cache pins, VM ownership and shared observation.

## Read and implement

Read complete `tests/integration/vm_control.py`, `online_snapshot.py`,
`system_runner.py`, `vm_transport.py` maintenance ownership/transport paths,
their cleanup regressions and the shared provisioner. Add explicit bundle/profile
selection and diagnostic generation records, read-only lost-reply reconciliation,
unchanged no-op and F15's transaction-wide launch barrier/process quiescence.
Reuse subset retirement; no second process scanner or signal-by-name path.
Do not acquire another owner's VM
or restart product/desktop services. Current public sync options are unimplemented
until this task registers help, dispatcher validation and scoped grants.

## Finite validation and cleanup

Run maintenance/provisioning safety regressions before a watched Ubuntu maintenance
history: use fixture A, change its host source, build B, sync only the necessary
closure and observe the changed harmless fixture witness in that same running
guest, without product actions/assertions. Record
unchanged boot/domain instance, baseline/app snapshot identities and preserved
unrelated guest state. Exercise repeat/no writes, corrupt/missing bundle refusal,
foreign-owner refusal and held fixture process refusal followed by explicit owned
quiescence/restart. Refresh provides diagnostics, not acceptance for an already
started scenario. Include a shrinking selection with obsolete launcher/trust
absence and shared files retained, plus a concurrent launch refused for the full
replacement/removal interval. Apply F50's attributed open/exec/trust witnesses,
daemon identity and private observer retirement. Prove effective barrier removal before
fixture B is used. Reuse unchanged F05 safety matrix proof; renew changed parts.
Test interrupted sync recovery, complete the owned maintenance
cleanup and pin release, and update maintained interfaces/guides through the
[master](../Fixture-Execution-Plan.md).
