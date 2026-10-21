# D01r — Review the named remote-desktop route

Acceptance: review

Required tasks: D01.
Estimate: 20–30 min.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract).

## Session boundary and deliverable

Extract the remote-provider review from D01. Select one named provider supported
on the declared Ubuntu/Fedora targets; inspect its real authentication, account
and session callers. Do not assume that it uses SSH or GDM's PAM stack. Record
the child's actual access, deliberate kiosk login attempt, prohibited desktop
result, smallest enforcement owner, enabled-service preconditions, working
ordinary-account remote desktop and normal kiosk entry controls, and restoration.

Keep provider/version/target applicability and automation readiness in the
existing design/catalogue owners. Identify missing public-provider bindings and
their finite qualification prerequisites for C07/D03. No absent service or failed
ordinary-account positive can count as a denial. If no provider can meet the
scope, retain the blocker and required decision rather than silently omit remote
coverage or broaden to all providers.

Deliver the remote map to D02 alongside D01's local map. No product changes,
provider setup or installed claims here; run links and plan metadata checks.
