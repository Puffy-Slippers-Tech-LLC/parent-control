# U04 — Recover entry after a temporary identity-check failure

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U03a.
Estimate: 45–90 min; session exception: one helper failure/restoration/reentry history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Read `run_kiosk_check` and its PAM callers in `tools/pam_oh_no_parent_control.c`,
the complete `tools/oh-no-parent-control-login-check` helper and
[service/identity authority](../SystemDesign/Kiosk-Confinement.md#service-and-routing-boundary).
Discover the existing helper/native PAM tests.

Select one transient helper/NSS unavailability condition from the actual call
chain. Establish whether restoration already permits fresh login; fix only a
demonstrated failure of bounded recovery or useful sanitized diagnosis. Do not
retry identity mismatches or parent authentication, turn helper errors into
success, extend deadlines indefinitely or require saved routing discovery.

Host controls retain error mapping, timeout/reaping and same-handle authorization.
Observe the installed operational failure separately from successful restored
passwordless entry, one approval/time result, exit/reentry and affected ordinary
login. A missing helper or wrong identity remains a safe operational refusal.
No NSS-provider matrix or new identity service. Run affected checks, required
review/build and restoration; close only U04.
