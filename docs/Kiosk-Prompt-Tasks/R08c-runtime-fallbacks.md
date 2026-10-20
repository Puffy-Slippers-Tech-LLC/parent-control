# R08c — Degrade optional runtime features

Acceptance: host

Required tasks: R08b — operational authentication-language fallback.
Estimate: 45–75 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master family B](../Kiosk-Resilience-Plan.md#acceptance),
[shared frontend flows](../SystemDesign/Frontends.md#main-flows)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract runtime presentation fallback from R08. Read complete startup,
`request_content.py`, shared form/resource loaders and optional audio,
notification/rich-report feature callers. Implement defaults or feature disablement
for missing/changed artwork, font and historical catalogue, unavailable optional
audio/notifications and rich reporting. Preserve the core form, child/parent
selection and genuine approval, including shared child-overlay behavior.
Keep executable/module/plugin/configuration authority distinct from cosmetics;
another layer cannot reclassify an omitted optional resource as mandatory.
Provisioning icons and native agent language are already owned by R08a/R08b;
original-cause collection and mixed recovery belong to R08.

## Acceptance and close-out

Select registered affected resource/startup/form unit/UI checks through maintained
launchers. Verify safe defaults, core request/approval dispatch and preserved
denial/cancellation behavior. No submission is authorized.
Apply master product review/revision, supported translations and final packaged-input
`make build`; record inputs for R08/R09a, update relevant owners and finish cleanup.
