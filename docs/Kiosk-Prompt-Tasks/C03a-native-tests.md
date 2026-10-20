# C03a — Reconcile native and package host tests

Acceptance: host

Required tasks: C03a1.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

C03a1 supplies native runtime dispositions. This slice audits account/PAM and
package composition/rollback coverage in test_fedora_pam.py,
test_package_configuration.py, mapped kiosk login/PAM units,
tests/support/kiosk_pam.py and tools/regression_unit.py. Include checked-in
fixtures and the old plan's staged, unstaged and untracked additions.

Map each to retained behavior, a port to the rebuilt owner, or an obsolete
implementation detail. Remove dead compilers/imports/registrations only after
all consumers are mapped. Retain ordinary-role authentication, rollback,
ownership and correct entry/exit checks. No customer outcome is weakened.

Run the exact affected unit selection through the maintained runner. Review
fixture resource/storage changes under their owners. Record source-to-test
dispositions in the existing design/test owner and hand shared interfaces onward.
