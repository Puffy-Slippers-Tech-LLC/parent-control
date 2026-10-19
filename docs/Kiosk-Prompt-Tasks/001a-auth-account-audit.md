# 001a — Audit authentication and account admission

Acceptance: review

Read the [master](../Kiosk-Prompt.md), lifecycle admission/account sections and
complete relevant provisioning, package PAM adapter, native account-gate and
login-check functions. Use `system_kiosk_admission.py`, first-configuration,
classification and PAM-variant owners for exact current coverage.

Map effective empty-token authentication, account ownership/expiry/quarantine,
PAM service/control flow, locks, saved session/actual transport and routing
repair/timeout failures. Separate accepted authentication from account/session
admission. Confirm the recorded incident from read-only evidence; do not enter
a password, change host authentication or run an installed test here.
Confirm the original incident's source-history attribution: the ambient-owner
rejection arrived with `eb0b7323`'s confinement helper on 2026-10-12; v1.0/v1.3
lack that helper. Distinguish this late-session regression from an authentication
failure or an unverified claim that password prompts existed since v1.0.

Update the master's existing audit with source/selector references, intended
public results, closed diagnostic coverage and concrete unknowns for 001b/001.
Include Fedora without-nullok and effective Ubuntu auth-policy checks. A module
presence check is insufficient. Preserve ordinary-account controls and package
interruption/reboot obligations. Do not expand into an arbitrary PAM matrix.

Acceptance is the finite auth/account portion of the failure map, with gaps
allocated or explicitly pending reconciliation. Validate changed Markdown links,
retain evidence in existing artifacts, finish owned cleanup and close only 001a.
Discovery inventories entry causes; it does not mandate new acceptance for every
existing unaffected account, PAM or package branch.
