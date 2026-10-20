# R08a — Degrade failed provisioning icons

Acceptance: host

Required tasks: R07 — policy-preserving authentication/session integration.
Estimate: 15–30 minutes.

Read the [master family B](../Kiosk-Resilience-Plan.md#acceptance),
[configuration decision](../SystemDesign/Lifecycle.md#r01d-configuration-and-quarantine-decision),
R05b's required-setup/release boundary and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract optional pre-GDM icon assignment from R08. Read complete
`accounts_service_set_icon_file()`, `accounts_service_provision_kiosk()` and
`packaging/lifecycle/postinst.in` callers through quarantine release. An invalid
or unavailable optional icon must record its cause, use the display default
without another required icon API call, and let required configuration complete.
Isolate icon get/parse/set errors only, bound the single optional attempt and
preserve retained custom artwork. Continue required visibility/routing/limit and
enforcement verification; no icon clearing/copy or successful reread is a fallback
prerequisite. Consume the separate product gate; never write native expiry.
Consume R05b's proven ownership/release interface; never release before required
enforcement or override administrator expiry. Runtime presentation is R08c.

## Acceptance and close-out

Use affected provisioning/package host checks for icon failure plus successful
required setup/owned release, a required-enforcement failure that retains quarantine,
and administrator-expiry preservation. Keep unrelated metadata unchanged. Require
master product review/revision, all supported translations for new strings and
`make build` after the final packaged edit. Record exact inputs/results for
R08/R09a and finish owned cleanup. Public pre-GDM recovery remains installed B.
