# Entry and session-control tasks

Apply the [shared execution and acceptance contract](README.md). Every row is
one task; budget includes its listed checks. `Host` does not mean VM-qualified.
Use the actual offered session route; never enter a desktop as a station shortcut.

Work in [accessible_ui.py](../../../tests/e2e/accessible_ui.py),
[ui_observations.py](../../../tests/e2e/ui_observations.py),
[kiosk_entry.py](../../../tests/e2e/kiosk_entry.py),
[desktop_session.py](../../../tests/e2e/desktop_session.py) and the corresponding
[GDM](../../../tests/integration/graphical_smoke/lib/onpc_gdm.pm),
[station](../../../tests/integration/graphical_smoke/lib/onpc_kiosk_entry.pm),
[session](../../../tests/integration/graphical_smoke/lib/onpc_desktop_session.pm)
and [journey](../../../tests/integration/graphical_smoke/lib/onpc_journey.pm)
workers. Keep provider selectors inside the explicit adapter. Reuse strict
ID lookup for owned controls. Do not require unused provider controls to be mapped.

| Done | ID / budget | Requires | Bounded deliverable and measurable acceptance |
| --- | --- | --- | --- |
| [ ] | P01 / 30 min | None | **Docs:** remove blanket external-ID refusal in Frontends and affected UI/GDM/search/prompt/viewer catalogue contracts. Preserve owned-ID requirements and generic-route retirement. Add missing MATE/DING rows; correct E2E README's stale no-ready-cases claim. All changed links pass; no readiness/status promotion. |
| [ ] | P02 / 40 min | Existing setup grants | **Preparation:** validate the maintained artifact/app-snapshot prerequisite, using `tools/prepare-appsnapshot --overwrite false` for test-only changes. Record available baseline/package identities; record provider versions/actual locale/layout as each surface is first observed. Acceptance: approved preparation succeeds and the owned lease is released. Missing setup is a reported blocker, never a baseline replacement. |
| [ ] | G01 / 55 min | P01 | **Host:** add the narrow nonsecret GDM adapter: account list, unique ordinary/station row, observed focus, ordinary password prompt, Escape and returned list. Check readily available IDs briefly, then use scoped semantics/keyboard. Existing kiosk stages consume the proof. Tests reject wrong owner, duplicate account labels, stale focus and list/prompt overlap; no secret API call is possible. |
| [ ] | G02 / 50 min | P01 | **Host:** replace unconditional complete-ID prompt preflight with session-specific prompt recognition/refusal for the station and desktop. Distinguish MATE, Shell Polkit, keyring and unknown modal surfaces; this task never authenticates or auto-dismisses them. Complete positive surrounding observations permit no-prompt results; ambiguous/incomplete/unknown prompts block input. Tests prove both routes and no action on a prompt. |
| [ ] | G03 / 40 min | G01, P02 | **VM diagnosis:** inspect only the offered station entry branch in the guarded envelope. Record whether session choice is offered and its public controls, or the destination of the default branch. Do not activate an unresolved choice. Ordinary-account selection reaches its prompt and Escape returns to the list. Collect evidence/cleanup; this observation task does not mark REQUEST01 ready. |
| [ ] | G04 / 50 min | G03 | **Host:** if a session chooser is offered, implement just that UI15 selection and independent selected-session readback; otherwise bind and document the observed passwordless default branch. Tests reject wrong/ambiguous session and unsupported branch, and consume one fresh input proof. No broad session catalogue. |
| [ ] | O01 / 45 min | G02, G04, P02 | **Owned-UI diagnosis:** reach the station through the guarded GDM route and inspect public application/form exposure. Acceptance is bounded evidence distinguishing missing application, missing form IDs, incomplete tree or working owned-ID observation, plus cleanup and a specific return condition. No backend readiness probe and no external-selector fallback for the form. |
| [ ] | O02 / 55 min | O01 | **Owned-UI host fix:** repair the smallest demonstrated observer/owned-accessibility defect, if any. A working O01 route needs only the corresponding regression check. Tests expose `kiosk-request-window` and required `kiosk-*` controls under the right owner, reject incomplete/duplicate/wrong-owner observations and return the immutable form projection. Classify any product change; schedule rebuild/preparation separately. |
| [ ] | G05 / 55 min | G04, G02, O02, current prepared assets | **VM:** run `tools/run-tests integration check_e2e_kiosk_entry`. Wrong ordinary entry is refused, station entry succeeds once, exactly one owned form exposes child/approver/duration/soft-app/messages and unavailable controls, and collection/cleanup pass. Independently supplied valid entry must be covered by the qualification. Record only REQUEST01/03's proven scope; case 57 remains pending. |
| [ ] | S01 / 50 min | G02 | **Host:** implement Shell desktop and session-menu resolution, then Switch User and logout confirmation targets. Prefer actions; otherwise observe each bounded keyboard focus step. Tests reject wrong session, ambiguous menu, disabled/hidden action and uncertain input; action success alone cannot pass destination checks. |
| [ ] | G06 / 55 min | G01 | **Host:** adapt existing GDM secret-recipient proofs to the qualified semantic route. Preserve wrong-account refusal, two fresh checks, sole empty masked focused field and single-use sealed input. Wrong-recipient, stale/reused-proof and capture/uncertainty tests pass. No change to the secret transport API or failure latch. |
| [ ] | S02 / 55 min | S01, G06, G04, P02; A01v if keyring appears | **VM:** run `tools/run-tests integration check_e2e_desktop_session`, which already uses separate Switch User and confirmed-logout attempts. Require actual GDM destinations, independent valid entry, refusal checks and cleanup for both. If measured runtime cannot fit one hour, split the two existing modes into two fixed qualification tasks before running; do not drop either branch. Returning to preserved desktop activity remains L04's separate acceptance. |

P01 targets [Frontends](../../SystemDesign/Frontends.md#public-automation-identities),
[building blocks](../E2E-Building-Blocks.md), and
[E2E README](../../../tests/e2e/README.md). Use
[test_accessible_e2e_ui.py](../../../tests/unit/test_accessible_e2e_ui.py),
[test_e2e_kiosk_entry.py](../../../tests/unit/test_e2e_kiosk_entry.py),
[test_e2e_desktop_session.py](../../../tests/unit/test_e2e_desktop_session.py),
[test_automation_ids.py](../../../tests/unit/test_automation_ids.py) and the
affected credential/cleanup checks. Add behavior tests where missing; do not
replace safety assertions with assertions matching the implementation.

After G05 and S02, resume existing customer tasks **013, 010/017 and 012**, each
under its own brief. Then implement/run **018, case 57** with its complete
selector lists, unavailable Request/no-authentication result and exits. Keep
owned selector implementation separate from external qualification. Do not
check 011 or promote a block merely because this plan or a host task is complete;
apply its existing live/regression/close-out gate.
