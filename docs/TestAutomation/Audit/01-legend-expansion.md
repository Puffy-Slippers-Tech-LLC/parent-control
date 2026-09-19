# 01 — Correct and independently verify legend expansion

**Recommended model: GPT-5.6 Sol. Effort: high.** This is a diagnosed mechanical
state-query correction with a small product accessibility addition.

**Prerequisite:** [Shared preflight](README.md#session-preflight-and-common-constraints).
**Status:** Complete. **Next:** [02](02-owned-ui-and-inventory.md).

## Scope and work

Read [ParentWindow](../../../parent/oh_no_parent_control_parent/main.py),
[overflow tests](../../../tests/ui/test_control_overflow.py), and the shared
[accessibility helper](../../../common/oh_no_parent_control_ui/accessibility.py).

1. Confirm the handoff diagnosis against the supported GTK state mapping:
   `Gtk.ToggleButton` active publishes `PRESSED`. Correct only the legend query;
   genuine checkboxes and switches keep their appropriate state checks.
2. Expose the expanded legend content through a stable public ID, proposed
   `parent-legend-content`, in `ParentWindow._legend_card`. Follow the existing
   product helper and parent application/surface scope, and reject collisions.
3. After normal toggle activation, wait for the correct active state and
   independently reacquire the content by ID and verify it is showing/reachable.
   The toggle's state alone cannot prove expansion. Preserve the content's meaning
   and the existing control/filter assertions at both scales. Use semantic
   navigation when needed, without geometry or hidden-control activation.
4. Keep the existing search existence guard. Do not fold unrelated identity or
   fixture work into this correction.

## Verification and completion

Run the focused identity/Parent units applicable to the changed ID, then:

```sh
tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_control_overflow.py'
```

Let the mandatory cleanup gate run. Both previously failing Parent cases must
pass with independent content evidence, and other assertions must remain intact.
If the correct state still leaves content inaccessible, preserve the result as
a potential product regression; do not relax the visibility assertion. Record
the final counts and runner artifacts. This narrow pass does not replace task
08's complete frozen UI run.

## Completion evidence

**Disposition:** Complete. GTK's supported accessibility mapping publishes an
active `Gtk.ToggleButton` through `PRESSED`. The Parent legend content now has
the public `parent-legend-content` identity, and the UI test reacquires and
reveals that identity before checking that it is showing. The required run also
retained the search existence guard and checkbox `CHECKED` assertions at scales
1 and 1.25. The shared accessibility helper publishes the native
`check.toggle` action for identified `Gtk.CheckButton` controls so those
assertions use an unambiguous public action while preserving GTK checkbox and
radio activation semantics.

Verification:

- `tools/run-unit-tests 'tests/unit/test_parent_main.py' 'tests/unit/test_automation_ids.py' -q`
  — 81 passed in 0.36s.
- `tools/run-ui-tests --timeout 1200s -q 'tests/ui/test_control_overflow.py'`
  — cleanup gate: 1,475 passed and 3 subtests passed in 81.26s; selected UI
  suite: 12 passed in 103.60s.

The completed legend cases retained their runner logs in
`/var/tmp/onpc-ui-preview-1hzra3s3` and
`/var/tmp/onpc-ui-preview-7_hbu88s`. There is no remaining Task 01 blocker.
Continue with [02 — Owned UI and inventory](02-owned-ui-and-inventory.md); the
complete frozen host UI run remains assigned to Task 08.
