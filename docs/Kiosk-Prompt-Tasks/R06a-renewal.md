# R06a — Renew owned kiosk infrastructure safely

Acceptance: host

Required tasks: R05 — integrated production admission/activation boundary.
Estimate: 90–150 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject), accepted
lifecycle decision, [selected states and ownership](../SystemDesign/Lifecycle.md#lifecycle-ownership-states-and-renewal),
[one readiness budget](../SystemDesign/Lifecycle.md#one-measured-entry-and-recovery-budget),
[cleanup safety](../../tests/README.md#cleanup-safety-prerequisites) and
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract infrastructure waits/renewal from R06; broker account isolation belongs
to R06b and approval/recovery association to R06. Read full manager/admission/
recovery callers. Implement declared bounded transient dependency waits and one
safe renewal of a proven owned stale/failed instance. Use the original deadline
through usable form/authentication readiness; no retry or unit start resets it.

Implement one owner's fresh/preparing/ready/in-use/failed/recovering transitions,
interruption-safe ownership/first-cause retention and accepted competing-login
wait/attach/conflict behavior. Preserve live visits, foreign/replaced state,
ordinary managers and inherited credentials. Never kill by blanket UID/guessed
PID or reset global logind policy. Initialize only proven new owned objects;
repeated entry/cosmetic drift cannot grow generations or require routine reboot.

## Acceptance and close-out

Run maintained host repeated-entry, transient/exhausted retry, stale/failed,
interrupted cleanup, live/foreign/replaced-session and descriptor/state-growth
controls. Apply resource/storage review and the master's product review/revision,
then final packaged-input `make build`. Update lifecycle/diagnostic owners and
record exact states, budget and callables for R06/R09b1. Finish owned cleanup;
actual GDM visit/renewal acceptance remains R10c1/R11c1.
