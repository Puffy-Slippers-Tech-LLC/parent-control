# C07a — Protect local desktop and TTY routes

Acceptance: host

Required tasks: C06.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-New-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Use C06's reviewed local-route entries and actual GDM/PAM/account callers.
Add only the missing narrow barrier to alternate desktop, terminal/TTY or
exposed local session selection; retain passwordless dedicated entry and all
ordinary-account login behavior.

Pair each defense with its normal-use and deliberate-child controls in targeted
host tests and existing installed-case bindings. If the baseline already
satisfies a route, verify and document that instead of adding restrictions.
Keep expected results and finite route parameters in their existing owners.
Run affected tests, independent product/backend review and final build.
