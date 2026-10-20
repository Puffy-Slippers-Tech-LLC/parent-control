# R09a — Compose compatibility histories

Acceptance: host

Required tasks: R08 — integrated fallback/recovery diagnostics.
Estimate: 60–90 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master A–C families](../Kiosk-Resilience-Plan.md#acceptance), R01's
ledger, delivered R02–R08 callables and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).
Apply [composition preflight](../TestAutomation/E2E-Building-Blocks.md#composition-preflight)
and the [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and deliverable

Extract finite A–C compatibility composition from R09. Reuse existing cases
267–269/290–294, `tests/system/test_enforcement.py`, `kiosk_entry.py`, canonical
ambient/required histories and `system_pam_variants.py`; inspect complete actual
callers and registration before naming a runnable selector.

Bind all master A–C inputs to public entry/approval/reentry, ordinary-role
controls and exact restoration: unrelated host contents/encoding/authority,
optional resources/services, pre-GDM icon/quarantine recovery, C-only native
authentication, real GDM credentials/umasks, saved-session repair and valid local
PAM variation. Carry R02b's unfamiliar callback forward. Locale-discovery failure
is an engineering control, distinct from genuine C-only installed approval.

## Acceptance and close-out

Use delivered shared operations; create no adapter campaign or duplicate history
engine. Repair only demonstrated supporting defects under resource/storage
contracts; new independent capability work needs a bounded prerequisite. Run
affected host composition/registration/restoration checks and record registered
selectors, inputs, public results and limits for R09. No VM acceptance occurs.
Apply master review/build/localization gates to product repairs and finish cleanup.
