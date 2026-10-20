# C02c — Prepare account and PAM integration

Acceptance: host

Required tasks: C02c2.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

C02c1 supplies account provisioning and C02c2 supplies owned lifecycle migration.
This slice reconstructs native PAM dispatch and distro integration only. Read
C01's mapped functions in tools/pam_oh_no_parent_control.c, the login check,
packaging/fedora_pam.py and their account/session consumers. Adapt the pinned
release's kiosk PAM branches to current supported distros explicitly.

Preserve ordinary users' authentication, session limits and privilege transitions,
kiosk passwordless entry, owned rollback/removal and unrelated packaging
improvements. Do not transplant the old GDM hook as current proof or import the
v1.4 parser/inventory framework as compatibility glue. Record unclosed ordinary
login routes for C06a rather than designing new defenses here.

Prepare the remaining PAM transaction with current consumers and direct
host composition/rollback tests. Keep the replacement unselected: C02 alone
switches the production PAM/account/package activation wiring. The existing
selected path stays coherent and buildable until then. Require independent
backend review and make build after final packaged edits. No host installation.
