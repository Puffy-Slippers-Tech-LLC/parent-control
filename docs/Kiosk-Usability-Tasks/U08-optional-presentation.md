# U08 — Keep requests usable when presentation resources fail

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Required tasks: U07.
Estimate: 45–90 min; session exception: one optional-resource fallback/restoration history per target.

Apply the [master contract](../Kiosk-Usability-Plan.md#per-task-acceptance-boundary).
Inspect actual optional artwork/style/notification consumers in kiosk startup
and provisioning, using [front ends](../SystemDesign/Frontends.md) and existing
fallback tests. Authentication language is already U01, not a second task here.

Select one demonstrated optional dependency whose failure prevents entry or
requests. Use a direct presentation fallback and preserve available features.
If no such defect remains, verify one representative existing fallback rather
than inventing a new restriction or broad resource-removal campaign. Essential
enforcement and genuine authentication are never optional presentation.

Host checks cover the exact fallback. On each target observe the representative
fallback leaving passwordless entry and a genuine approved request/time result
usable, then restore normal presentation. No screenshot/style acceptance matrix,
feature catalogue, notification campaign or all-language sweep. Run affected
checks, required review/build and owned cleanup; close only U08.
