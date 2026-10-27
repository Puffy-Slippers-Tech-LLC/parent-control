# C07r3 — Check ordinary remote desktop use

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C07r2.
Estimate: 20–30 min, including owned restoration.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).
C07r2 supplies the qualified safe remote connection and its C07r1 preparation.
This task owns only the ordinary-account slice of the
[remote qualification gap](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap).

## Session boundary and deliverable

Use the standard Jordan fixture, permitted to use the desktop and logged out of
other graphical sessions. Through the qualified GNOME Remote Desktop system
connection, perform real remote GDM account authentication, reach a usable full
GNOME desktop and exercise one normal public desktop launch/control. Observe
its result through that same remote connection, independently tied to Jordan's
UID and remote session. Qualify the remote input recipient and desktop/result
binding for reuse by C07r4. A local desktop, process census or handshake alone
is insufficient. No station attempt, product edit or retained-session branch
belongs here.

## Implementation and checks

Use the [reviewed ordinary positive](../SystemDesign/Kiosk-Confinement.md#finite-checks-restoration-and-d02-handoff),
[external-provider qualification owner](../TestAutomation/E2E-Building-Blocks.md#external-provider-qualification),
[shared support guide](../../tests/support/README.md) and
[credential contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary).
Reuse C07r2's shared operations and guards; extend the existing remote adapter
rather than adding a case-specific transport. Discover current source and
registrations before reading them. This slice's selector is **planned and
unregistered** until implemented and qualified.

On both targets, observe authentication, the selected full desktop/session and
one usable public control result through the remote client. Record the exact
provider/client tuple, locale/keyboard and selected session in the existing
catalogue and normal output. Reuse the shortest public result journey under the
[UI mandate](../Mandates/UI-Automation-Mandate.MD#result-oriented-test-scope).
Use 120-second connection, challenge, post-input result and per-operation cleanup
deadlines, retaining the existing 1800-second outer worker limit and human-time
distinction. Split independent missing mechanics before implementation if needed
to fit the budget.

Log out only the owned remote session through the shared public system route;
independently observe its end. Restore owned provider/network/settings changes
and remove owned secrets under the
[storage contract](../Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
Preserve unrelated sessions and configuration. Apply the
[test scope mandate](../Mandates/Test-Scope-Mandate.md); do not repeat shared
safety matrices or add tests of briefs/history. A failed positive or cleanup
keeps this task open. This qualification grants no C07 or C11f/C12f acceptance.
