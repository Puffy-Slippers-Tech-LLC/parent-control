# R01d — Settle configuration and quarantine ownership

Acceptance: review

Required tasks: R01b — effective administrator policy.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[configuration target](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary and route

Extract pre-GDM account setup from R01. Read complete
`packaging/lifecycle/postinst.in` and `tools/provision.py` provisioning,
`accounts_service_provision_kiosk()`, `accounts_service_set_icon_file()`,
`repair_kiosk_visibility()` and cache-version/transaction/expiry callers. Trace
failure and retry through actual public visibility and quarantine release.
Runtime/broker readiness and update activation belong to R01e.

## Deliverable and acceptance

Choose narrowly verified capability/schema behavior or a public visibility-repair
route, preserving unrelated account fields and ordinary users. An unfamiliar
compatible version is not a veto; an unknown schema must not be written blindly.
Separate optional icon assignment from required enforcement/setup; its fallback
uses the display default without needing another successful icon API call.

Define transaction/field ownership for temporary quarantine, captured prior
expiry, interruption and later administrator denial. Resolve the same-value
administrator-write ambiguity: equality with the saved expiry alone proves no
ownership. Require bounded product recovery without overriding effective policy.
Assign visibility implementation to R05a, quarantine to R05b and icon degradation
to R08a. Add each real pre-GDM rejection to the single ledger with controls,
sanitized cause and exhausted safe-recovery alternatives. R01 reviews the
integrated mechanism; this task implements nothing. Check changed links and
documentation consistency; preserve existing evidence and no runtime resources.
