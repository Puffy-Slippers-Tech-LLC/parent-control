# C07r2 — Connect safely to remote sign-in

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: C07r1.
Estimate: 20–30 min, including owned restoration.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../TestAutomation/E2E-Execution-Contracts.md#capability-acceptance).
C07r1 supplies repeatable provider preparation, not a retained running session.
This task owns only the safe-connection slice of the
[remote qualification gap](../TestAutomation/E2E-Building-Blocks.md#remote-login-qualification-gap).

## Session boundary and deliverable

Implement and qualify one fixed client → system RDP authentication → redirection
→ identified remote GDM connection. Bind the target VM, client, remote display,
session and greeter owner. Reuse the guarded attempt/credential envelope and
shared external-provider adapter; local `seat0` discovery or local-screen key
delivery cannot stand in for the remote connection. No product changes or
ordinary-account desktop qualification belong here.

Follow the [provider exception and identity rules](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception)
and [credential contract](../../tests/e2e/README.md#credential-staging-and-password-capture-boundary).
Qualify intended recipient, wrong/ambiguous recipient refusal, an empty masked
field, fresh same-challenge proofs, single-use input and uncertain-input refusal
at the shared boundary. Keep system RDP credentials distinct from Linux account
authentication. Never replay uncertain input or expose secrets in captures.

## Implementation and checks

Read the [actual provider/session path](../SystemDesign/Kiosk-Confinement.md#authentication-and-selected-execution-boundary),
[external-provider qualification owner](../TestAutomation/E2E-Building-Blocks.md#external-provider-qualification)
and [shared support guide](../../tests/support/README.md). Local helpers in
[session control](../../tests/e2e/session_control.py) and
[the UI adapter](../../tests/e2e/accessible_ui.py) are reuse candidates, not remote
qualifications. Discover any other source and registrations first. The remote
selector is **planned and unregistered** until implemented and qualified.

On both targets, reach the actual remote greeter through the redirect-capable
client and independently establish its session/owner binding. Exercise the
necessary shared input refusals without duplicating guard matrices in consumers.
Do not count a handshake alone as successful remote greeter acquisition.
Record exact GRD/GDM/Shell/client revisions, locale and keyboard in the catalogue
and normal output. Use 120-second connection, challenge, post-input result and
per-operation cleanup deadlines; preserve the 1800-second outer worker bound
and exclude human decision time from machine-stage assertions.

Apply the [test scope mandate](../Mandates/Test-Scope-Mandate.md). Use maintained
preparation and [owned storage](../Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
Close only recorded client/remote-session identities, restore owned provider and
network changes, remove owned secrets and preserve foreign state on both targets.
If safety qualification needs an independent slice to fit the budget, insert it
before implementation. Missing identity, timeout or incomplete cleanup leaves
this task open. Qualification supplies no consumer desktop acceptance credit.
