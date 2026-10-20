# R07 — Tolerate authentication and session configuration

Acceptance: host

Required tasks: R06.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md), its R01 contract and R06 recovery
result, the [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [account boundary](../SystemDesign/Kiosk-Confinement.md#admission-and-account-integrity).

## Purpose and route

Make valid local authentication/session variation compatible with passwordless
request-station entry while preserving effective administrator access policy,
ordinary-account authentication and genuine parent approval.
Read complete affected functions and their callers, callees and shared state in
`packaging/kiosk_confinement.py`, `packaging/fedora_pam.py`,
`tools/pam_oh_no_parent_control.c`, `tools/oh-no-parent-control-login-check`
and the native/session paths selected by R01. Follow activation and rollback
callers through the [lifecycle owner](../SystemDesign/Lifecycle.md).

## Finite deliverable

Implement only the R01 mapping for valid PAM include/module variation, harmless
formatting, actual GDM credentials/umasks and saved-session repair. Preserve
explicit denial, expiry and parent denial/cancellation; never enable global
null-token authentication or bypass ordinary accounts. Isolate unnecessary
callbacks instead of treating unknown module names/configuration as hostile.
For every remaining entry rejection, complete the master's rejection ledger:
concrete reachable risk or actual essential setup/administrator policy, failed
recovery alternatives, positive control, negative control and sanitized cause.
Do not introduce basename-only security or a universal host executable allowlist.

## Validation and close-out

Use registered affected checks in `test_kiosk_login.py`, `test_fedora_pam.py`,
`test_system_pam_variants.py`, native entry tests and relevant package tests;
inspect actual registration and select the lowest effective maintained scope.
Pair tolerated variation with explicit-denial and unchanged ordinary-role
controls. Public installed proof remains R10/R11; host counts grant none.
Apply the master's mandatory Astra review/revision gate to product fixes, run
`make build` after the final packaged-input edit, and translate new product
strings into every supported language. Preserve owned cleanup and pre-existing
work; close only R07 with exact input/check evidence and advance the pointer.
