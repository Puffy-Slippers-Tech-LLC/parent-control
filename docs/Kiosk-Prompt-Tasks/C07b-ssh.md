# C07b — Protect kiosk SSH access

Acceptance: host

Required tasks: C07a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Trace the SSH admission route named in C06a through the actual account/PAM
integration. Add only the missing kiosk-specific barrier; preserve permitted
ordinary-account SSH authentication and product approval privilege transitions.

Maintain targeted host tests and the exact installed negative/ordinary-account
positive binding, including service-enabled preconditions and restoration.
No global null-password policy or unrelated-user denial. An absent SSH service
cannot establish the negative. Already effective baseline controls need proof,
not duplicate code. Apply independent product/backend review and final build.
