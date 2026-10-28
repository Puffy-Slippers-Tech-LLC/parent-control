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

Selected history: temporarily hide only the installed
`kiosk-background-scenery-clear.png` while the station is inactive. The existing
loader catches the missing image and floating scenery falls back to the static
background. Verify fresh passwordless entry, a usable form, genuine approval
and independent Parent time readback; restore the exact image and verify fresh
usable entry with normal resources. No product change is currently indicated.
Run the existing missing-artwork check in `tests/unit/test_floating_islands.py`
and a finite installed binding at the existing graphical qualification owner.
The registered selector is `check_e2e_kiosk_optional_artwork`. The first attempt
on both targets reached the usable missing-image form but the test worker refused
its new authentication binding before password entry. The exact binding is now
registered; focused credential/request regressions and source checks passed.
The retry passed genuine approval and independent time readback. Its restored
reentry check incorrectly reused the pre-approval balance for a second estimate
comparison; the finite journey now uses the existing usable-form reentry rule
while retaining the independent grant comparison. A clean two-target retry and
owned cleanup remain required; no installed acceptance is claimed yet.
