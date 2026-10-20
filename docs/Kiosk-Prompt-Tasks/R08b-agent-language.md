# R08b — Keep native authentication usable without translations

Acceptance: host

Required tasks: R08a — optional provisioning completion.
Estimate: 20–30 minutes.

Read the [master family B](../Kiosk-Resilience-Plan.md#acceptance),
[native-language contract and selected fallback](../SystemDesign/Localization.md#r01e-native-authentication-fallback-decision),
[approval lifetime](../SystemDesign/Broker.md#prospective-kiosk-approval-lifetime)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract native authentication-language fallback from R08. Read complete
`KioskAgentLocale.prepare()` in `kiosk/oh_no_parent_control_kiosk/agent_locale.py`,
form preparation/request callbacks and necessary job/agent/session callers.
Implement safe native/untranslated authentication for C/C.UTF-8-only hosts,
missing native catalogues and failed locale discovery. Separate cosmetic locale
preparation from operational, correctly associated agent readiness; never treat
a failed job/stale agent as ready or let a late callback authorize a new visit.
Preserve selected-parent authentication and the original recovery deadline.

## Acceptance and close-out

Use R01's accepted mapping before adapting the C-only refusal expectation in
`tests/unit/test_request_time_estimate.py`. Run affected locale/preparation/form
checks for fallback, missing discovery/catalogue, job/cancellation order, ready
agent and request dispatch. Require master product review/revision, supported
translations for new strings and final packaged-input `make build`. Update the
localization owner and record exact inputs/callables for R08/R09a; finish owned
cleanup. Real C-only genuine approval remains installed B on both targets.
