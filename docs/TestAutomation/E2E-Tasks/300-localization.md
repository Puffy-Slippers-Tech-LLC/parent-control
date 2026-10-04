# 300 — Chinese latest-install kiosk lifecycle

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **006** — Verified current-package installation through LIFE04, with independent completion and reboot notice.
- **007** — Customer reboot through LIFE02 and independent fresh-boot observations.
- **300a** — Chinese baseline assets and independent FIX06 verification.
- **300b** — DESK13 child desktop-language setting, independent readback and session renewal.
- **300e** — Chinese pre-reboot and untouched chooser/default/form observations.
- **300f** — Real Chinese MATE authentication and approval/result across fresh kiosk sessions.
- **300k** — Fresh-install, single-reboot composition of the Chinese first-presentation observations.

Estimate: 40–60 minutes.
Session exception: Latest-package installation, the unchanged-boot Chinese notice, one reboot and two genuine approvals across fresh kiosk sessions remain one continuous customer history.

## Scope and acceptance

Implement exactly the [Chinese kiosk lifecycle recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300)
as one complete case. Start product-free; verify Chinese baseline assets and
one latest current-source package. Use DESK13 for Jordan's `zh_CN.UTF-8`
desktop language and explicit session renewal. Keep Jamie and the station
desktop languages English, with Jordan's personal product language unset.

Install the current package once using LIFE04 and independently observe
completion, installed version, reboot notice and unchanged boot. Enter kiosk
before Parent setup or any automatic language handler. Require Jordan as the
default child and the actual Chinese reboot-required message/buttons before
any chooser can displace it. Reboot once through LIFE02 in the same attempt.
After only necessary public policy setup, observe the untouched Chinese
chooser, Chinese default and initial form for Jordan before saving anything.
Cancel without saving to read the form, then explicitly save Chinese through
public Preferences.

Perform two ordinary 75-second, soft-app-included requests to Jamie across
normal kiosk exit and fresh re-entry. Require actual Chinese native MATE
PolicyKit buttons, system explanatory/password text and product request message
on both challenges. Observe real approval, translated success and the expected
public time/policy result, with retained checked Chinese language and unchanged
account names and request values. Follow all exact phase assertions in the
recipe; neither an English approval nor a mocked/product-only prompt suffices.

## Shared implementation

Reuse the current-only LIFE04 path and LIFE02, FIX04/FIX06, DESK13 and LANG01.
Chinese assets belong to baseline preparation; attempts verify them. Reuse
`ChineseKioskJourney` initial-presentation operations in
[chinese_kiosk_lifecycle.py](../../../tests/e2e/chinese_kiosk_lifecycle.py),
`request_flow.chinese_request` / `onpc_request_flow::prepare_chinese` and
`kiosk_approved_flow.chinese_approval` / `onpc_request_flow::approve_chinese`.
The case supplies finite values, public return and persistence comparisons;
shared operations own selectors, lifecycle and authentication mechanics.

Task 300e's historical upgrade qualification and 300f's two Chinese approvals
remain scoped evidence in the [catalogue](../E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
Task 300k qualifies the changed current-install composition. Reuse current
callables and valid evidence, never the old qualification's dual-package
lifecycle or restored attempt.

## Session boundary

The original task combined several independent customer histories and missing
surface/result bindings. Its remaining composition is the uninterrupted Chinese
history above. The [acceptance decomposition](../E2E-Scenario-Recipes.md#personal-language-acceptance-decomposition)
preserves every original obligation in tasks 306–310, with bounded prerequisite
qualifications; no multilingual, RTL, offline, draft, countdown or translated
approval assertion is dropped.

Task 300j retains its own German/Hebrew restoration qualification unchanged.
After it closes, the next task is 300k, then this Chinese case. This session
does not execute those later tasks. Current briefs/recipes supersede the old
saved task-300 handoff's combined-case and Chinese-upgrade wording; preserve
launcher checkpoints and historical evidence.

## Implementation entry

One planned case; no numeric coverage ID or executable is registered.
After composition preflight, allocate exactly one stable numeric coverage ID,
scenario family and executable for the complete linked recipe. Qualify any
newly discovered shared binding before registration and live acceptance.
Run that exact case through the maintained E2E launcher and regenerate coverage
at close-out. Missing current package inputs or a genuine reboot-required
result remains a blocker; do not simulate a notice, reinstall or introduce an
older release. No complete-case attempt or acceptance is claimed.
