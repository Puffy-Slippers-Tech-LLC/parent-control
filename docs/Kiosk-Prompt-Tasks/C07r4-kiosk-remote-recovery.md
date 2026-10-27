# C07r4 — Check kiosk remote sign-in and recovery

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C07r3.
Estimate: 20–30 min, including owned restoration.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).
C07r3 supplies the ordinary remote positive and its qualified connection and
preparation. This is the final pre-edit slice of the
[remote qualification gap](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap).

## Session boundary and deliverable

Consume the qualified ordinary positive, then reconnect through the same working
GNOME Remote Desktop system provider. Identify `oh-no-parent-control` at remote
GDM and attempt sign-in without a kiosk password. Select a full desktop if
publicly offered. Independently observe the actual authentication refusal and
absence of a station desktop, or a usable request-only destination. Bind the
actual distro PAM path and remote session/result. If authentication stops before
selection, record that no desktop command started; invent no selected-command
denial. Do not change kiosk credentials, bypass authentication, disable the
provider or edit product code.

## Implementation and checks

Follow the [reviewed finite history](../SystemDesign/Kiosk-Confinement.md#finite-checks-restoration-and-d02-handoff)
and [D02's existing-barrier decision](../SystemDesign/Kiosk-Confinement.md#frozen-implementation-boundaries).
Reuse C07r1–C07r3 operations and the
[short confinement usability history](../TestAutomation/E2E-Building-Blocks.md#short-confinement-usability-history).
Discover source and registrations before reads; the station remote selector is
**planned and unregistered** until implemented and qualified. Follow the
[UI mandate](../Mandates/UI-Automation-Mandate.MD) and
[credential contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary);
product reads/actions use the shared Application UI API, external authentication
uses the guarded remote adapter.

On both targets, pair the station attempt with the working ordinary positive,
repeat that positive after the attempt, and run the complete short local
passwordless entry/approval/rejection/Cancel/exit/reentry history. Qualify remote
absence/results independently of client return codes or internal account probes.
Record exact versions, locale/keyboard, actual authentication/selected-session
disposition and public result in the existing catalogue and normal output.
Preserve 120-second machine-stage and per-operation cleanup deadlines, human-time
distinction and the existing 1800-second outer worker envelope. Split independent
work before implementation if the slice cannot fit its budget.

Restore only owned provider, TLS/secret, network, session and public settings
changes through maintained routes under the
[storage contract](../Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
Verify permitted remote/local use before restoring original service enablement
and activity. Preserve foreign sessions and inputs. Apply the
[test scope mandate](../Mandates/Test-Scope-Mandate.md); add no brief/history tests
or duplicate safety matrices. A failed ordinary positive, timeout or missing
observation is inconclusive. A demonstrated station full desktop is a product
mismatch to retain for C07, not a qualification pass. Finish both-target cleanup;
this task supplies no consumer or C11f/C12f acceptance credit.
