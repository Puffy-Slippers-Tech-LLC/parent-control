# D00a2 — Remove service-name admission rejection

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: D00a1, D00a2q, D00a2r.
Estimate: 30–60 min; session exception: one admission fix, review/build and both-target usability.

Apply the [desktop task contract](../Kiosk-Desktop-Plan.md#task-execution-contract),
[shared task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).

## Session boundary and deliverable

D00a1 supplies the short complete public gate. D00a2q supplies the real graphical
service-variation binding and its target-specific qualification. D00a2r supplies
the qualified reached prohibited-route control through
`su_service_route.qualify(transport, lease)` and
`check_e2e_kiosk_service_route` on both targets. It requires the real child-run
`su-l` native account refusal, same-route ordinary positive and restored normal
station entry; reuse that binding for the affected control after this product
edit. No product source changed and
neither target has received D00a2 acceptance. Resolve only the
[audit's service-name allowlist](../SystemDesign/Kiosk-Confinement.md#admission-refusals-and-recovery-owners)
in [native PAM](../../tools/pam_oh_no_parent_control.c) `kiosk_identity`,
`pam_sm_acct_mgmt`, `pam_sm_open_session` and the direct dispatch in
[login-check](../../tools/oh-no-parent-control-login-check) `main`.
Read complete affected callers and distro PAM consumers via the design map.
Unknown graphical-service naming alone must not reject passwordless access to
the dedicated request app. Preserve ordinary-user time checks, same-handle
account/session authority, bounded helper execution and lifecycle leases.
Saved-routing discovery belongs to D00a3; lease recovery remains D00a.

Before editing, bind D00a2q's qualified real `gdm-autologin` operation and its
current result on each target. Its pre-fix account refusal supplies route/refusal
qualification only; actual selected app execution remains this product fix's
required positive. Reuse `gdm_service_variation.qualify(transport, lease)` and
the registered `check_e2e_kiosk_service_variation` envelope, replacing the
qualification class's current-refusal assertion with a requirement for
`app_execution_qualified == True` after the fix. Preserve its invocation witnesses,
public form reads, selected-process observation and exact restoration.
Pair the repaired predicate with
one specifically reached prohibited route and a benign adjacent/unknown
service-name control. A synthetic PAM name or saved session default is not
proof of actual execution or an attack. Keep only justified narrow refusals;
do not make arbitrary PAM invocations successful unrestricted sessions. Record
the caller/action, child control, distinguishing predicate and public results in
the design owner. New desktop/terminal/SSH protection campaigns retain their
existing owners; do not absorb them into this fix.

Reuse [prepared PAM regressions](../../tests/unit/test_prepared_kiosk_pam.py),
[login regressions](../../tests/unit/test_kiosk_login.py) and
[installed admission](../../tests/integration/system_kiosk_admission.py)
`pam_callback`/`probe`/`verify` for directly affected engineering checks. The
current installed 268 checks account routing only and does not qualify the
new graphical variation. Resolve any missing independent operation/provider
qualification as a small prerequisite before product editing; mark new
bindings unqualified until their real target results pass.

Obtain independent Astra xHigh backend review, run affected product checks and
`make build` after the final packaged edit. On the exact candidate, run the
D00a1 registered short history on both targets, the actual repaired graphical
variation and its paired control, and ordinary-account graphical login. A
password prompt, rejection loop, unusable form or failed positive leaves this
task open. Apply the [test scope mandate](../Mandates/Test-Scope-Mandate.md),
restore attempt-owned service/session configuration and finish owned cleanup.
Record the residual disposition and short result in the existing design owner;
no later task supplies this fix's missing installed gate.
