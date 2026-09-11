# Task 20 — fresh-input authentication attempt refused by a later source addition

## Result and boundary

Authenticated VT6 attempt 12 captured the current checkout after the unrelated
`docs/VersionHistory.md` addition, then refused `provenance:source-changed` during
preparation before worker startup. Three new, nonignored release-tool files under
`tools/` were absent from the pre-attempt status and were created together at
08:51:41 local time while the guarded controller was running. Their addition
changes the enumerated source path set and is sufficient to explain this attempt's
refusal. The controller does not export a full snapshot comparison, so the evidence
does not prove that no other field changed or explain older provenance failures.

Source activity continued after cleanup: the release-signing module changed
again, two new launchers changed mode, two existing release helpers changed and
another nonignored publishing module appeared. These later changes did not cause
the already-finished attempt, but they establish a current writer rather than a
settled fresh-input set. Preserve all of that work. Task 20's return condition is
a later session preflight showing that this release-tool work has stopped and no
new source path or metadata change is in progress.

This is current concurrent-source evidence, not a VM/lease failure and not a
reason to weaken `VerifiedInputs`. Preserve the new files. Capture all current
nonignored inputs in the next attempt after reconciling that no later addition is
in progress. Until that return condition is met, Task 15A is the next independent
ready checklist entry. Do not reuse attempt 12's captured inputs or treat its
lack of worker startup as authentication evidence.

Reuse the [provenance contract](../../../tests/e2e/README.md#controller-owned-provenance),
[worker contract](../../../tests/e2e/README.md#shared-guarded-worker),
[VT6 contract](../../../tests/e2e/README.md#visible-vt6-installation-terminal) and
[reuse map](../Reuse-Map.md#installation-helper-and-open-limits).

## Verification and retained evidence

The explicit cleanup-safety selection passed **694 tests and 3 subtests**; the
privileged dispatcher repeated the same passing prerequisite. The guarded route
was `tools/run-tests integration check_graphical_vt6_authentication` and exited 1.
Outer result: `/tmp/onpc-graphical-smoke-w7hm7ov_/result.json`; qualification
events: `/tmp/onpc-e2e-evidence-sc7il6f5/`.

The result records baseline digest
`cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`,
267.537 seconds total, 197.961 seconds preparation and 69.522 seconds cleanup.
Infrastructure failed `provenance:source-changed`; product and collection are
`not-run`. Cleanup passed, lease phase is `complete`, baseline restoration and
host preservation passed, and source preservation correctly stayed false. A
fresh guarded status check found the pinned VM off. All commands exited; there
is no owned process, callback, display, screenshot export, lease or recovery
obligation and no approval or Polkit denial.

Attempt 11 remains the passing authenticated worker/shutdown evidence inside a
failed outer qualification. Attempt 12 neither contradicts nor extends that
worker scope. Complete authentication qualification, sudo/notice pixels,
E2E-002 and both E2E-028 startup-fault variants remain unaccepted.

Actual settings: **`gpt-5.6-sol` / `high`, Standard**.
