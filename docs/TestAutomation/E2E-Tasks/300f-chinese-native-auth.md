# 300f — Qualify Chinese native kiosk authentication

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **019** — Fixed kiosk prompt ownership, selected-parent/request context and fresh empty masked recipient proof.
- **021a** — Prepared ordinary kiosk request, one real approval and independent automatic exit/result composition.
- **300a** — Installed Chinese authentication translations, locale and fonts with read-only FIX06 verification.
- **300e** — Chinese initial kiosk language/default observations and the shared first-presentation binding.

Estimate: 20–30 minutes.

## Scope

Qualify the Chinese MATE provider binding needed by the last two phases of
[the Chinese kiosk lifecycle recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300).
Use Jamie/Jordan, `zh-Hans` and two ordinary 75-second soft-app-included requests,
one per fresh kiosk session. Keep the administrator and station desktop
languages English. Require actual Chinese native Authenticate/Cancel buttons,
system-owned explanation/password label and product request context before
credential input on both prompts. Preserve real approval and public result/exit
behavior. Locale environment readback, English provider evidence or a translated
product message alone cannot qualify the binding.

Behavior owner: [personal language selection](../../SystemDesign/Frontends.md#personal-language-selection).
Apply [external-provider execution](../E2E-Execution-Contracts.md#external-provider-work-within-the-sequence)
and reuse the [MATE qualification](../E2E-Building-Blocks.md#external-provider-qualification)
and [Chinese provider gate](../E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
Keep the native agent and system translations unmodified.

## Implementation entry

Read the [support guide](../../../tests/support/README.md),
[bounded supporting work](../E2E-Building-Blocks.md#keep-supporting-work-bounded)
and [composition preflight](../E2E-Building-Blocks.md#composition-preflight).
Start at these complete callables and follow affected dependencies:

- [accessible_ui.py](../../../tests/e2e/accessible_ui.py): `mate_prompt`,
  `mate_challenge_identity`, `wait_mate_prompt`, `mate_prompt_refusals`,
  `mate_field_proof`, `mate_provider_metadata` and `kiosk_mate_approval`.
  Extend a finite Chinese binding while preserving English provider guards;
  reuse recorded semantic discovery rather than inventing provider IDs.
- [mate_prompt.py](../../../tests/e2e/mate_prompt.py) and
  [kiosk_approved_flow.py](../../../tests/e2e/kiosk_approved_flow.py): existing
  declared prompt and successful request fragments. Reuse shared mechanics,
  not a qualification's private fixture lifecycle.
- [request_flow.py](../../../tests/e2e/request_flow.py), shared language chooser
  operations and 300e's delivered initial-entry binding. Preparation uses
  current installed state and supported public actions; do not repeat the
  upgrade history or depend on a previous task's saved VM state.
- [Credential/capture contract](../../../tests/e2e/README.md#credential-staging-and-password-capture-boundary),
  the existing protected worker and same-challenge proof/dispatch. Preserve
  single-use delivery, capture sealing and fresh recipient ownership.

## Acceptance

1. In a fresh owned installed attempt, independently verify Chinese FIX06,
   enter the declared kiosk profile and select/save Chinese through public
   controls. Confirm Jamie/Jordan/75-second/soft-included choices independently
   before the single REQUEST09 submission.
2. On the actual native prompt, independently require Chinese system-owned
   buttons, explanation and password label plus the complete Chinese product
   request. Qualify provider/session ownership, selected parent/context and
   the sole empty masked focused field; recheck the same challenge before one
   credential delivery. Require explicit real approval and the ordinary
   Chinese granted result/automatic usable-GDM return.
3. Enter a fresh kiosk session without another reboot or station/administrator
   language change. Require persisted Chinese choice, Chinese form and no
   first-run chooser, then submit a deliberately new identical request. Prove
   the new agent/challenge's native Chinese strings and recipient again before
   one real approval, followed by independent result and normal exit.
4. Preserve wrong-owner/recipient/context, ambiguous/hidden/disabled/unfocused/
   nonempty/stale-field and replaced-challenge refusals without credential
   release or later input. Exercise nondefault language and fresh-session
   identity through the actual decoder/worker/recorder. Record actual provider
   version, locale and keyboard tuple in sanitized evidence. Pass capture
   reconciliation, collection, worker/callback shutdown, owned cleanup,
   baseline restoration, finalization and host/source preservation.

Planned selector (unimplemented; register and cleanup-test before use):

```bash
tools/run-tests integration check_e2e_chinese_native_auth
```

Run affected prompt/secret/worker/language and recorder safety checks before live
qualification on every enabled VM. Require `check_e2e_kiosk_approved_flow` as the
affected English MATE/request regression. Retain any further affected regression
under the shared live policy and the session's first-new-live-failure boundary.

## Session boundary

This allocation supplies no implementation, Chinese provider qualification or
complete-case credit. The fresh installed profile qualifies the finite native
binding only. Task 300 still owns the continuous genuine upgrade/no-reboot
prompt/reboot/first-kiosk/approval/re-entry/approval history and the existing
multilingual/RTL acceptance in one complete case.
