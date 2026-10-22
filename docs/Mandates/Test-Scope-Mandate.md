# Test scope mandate

This mandate owns whether coverage is warranted and how much to add or retain.
Apply it when planning, adding, changing or reviewing tests, including test
infrastructure work and automated repair. [Test maintenance](../../tests/README.md)
owns execution and failure handling; the [UI mandate](UI-Automation-Mandate.MD)
owns permitted automation routes. Task briefs cannot require excluded coverage.

## Required coverage

- **Product behavior must be tested.** Protect meaningful customer outcomes,
  authorization, enforcement, saved state, recovery and supported lifecycle
  boundaries at the lowest effective layer. Retain installed checks where the
  actual integration or customer journey is necessary.
- **Core test infrastructure and tools must be tested.** Protect guarantees
  whose failure could produce a false pass, run the wrong selection, corrupt
  evidence, expose credentials or damage accounts, processes, files or VMs.
  Examples include runner dispatch and verdicts, shared input/ownership guards,
  fixture integrity, evidence handling and owned cleanup/recovery. Test these
  guarantees directly through focused unit or integration checks.

Being located under `tests/` or `tools/` neither requires nor exempts coverage.
The behavior and consequence of failure determine the need. A shared helper
implementing a core guarantee belongs to core infrastructure; an ordinary case
helper, test data builder or assertion wrapper does not become core merely
because other tests use it.

## Limits

- Do not automatically add tests for test cases, assertions, doubles, private
  fixtures or helpers. Verify ordinary test changes by running the affected
  tests. Add a separate infrastructure regression only for a concrete core
  guarantee above that existing coverage does not already protect. Stop there;
  that regression creates no obligation for another layer of tests around it.
- Do not add or retain UI tests of test tools, including dashboards, watchers,
  evidence viewers and fixture control panels. Exercise any core dispatch,
  recording, storage, input-safety or cleanup guarantee beneath their UI.
  Product UI tests may use graphical fixtures and automation; the tool's own
  widgets, navigation, rendering and presentation are not acceptance targets.
- Reuse existing coverage before adding a case. Use representative inputs and
  meaningful failure boundaries; add combinations only for distinct interacting
  behavior. Do not mirror each implementation branch, function, helper or
  consumer with a separate test, duplicate a shared guarantee in every case,
  or add tests solely to increase counts or coverage percentages.
- Keep validation proportional to the change. Run the smallest affected
  selection through maintained launchers. Do not run tests of the runner as a
  prerequisite to ordinary product tests or repeatedly requalify unchanged
  infrastructure. Documentation-only policy edits need document checks, not
  new tests asserting the policy's wording.

## Review and reduction

For each proposed test, identify the product outcome or core infrastructure
guarantee it protects, the distinct failure it detects and why existing coverage
is insufficient. Keep this explanation in the normal change description when
needed; do not create a separate checklist, evidence file or test for it.
If no concrete gap exists, do not add the test.

Apply the same rule to existing coverage during maintenance. Remove test-tool
UI tests and redundant recursive checks rather than moving their entire
matrices to another layer. Preserve any unique core guarantee with the smallest
effective direct check; preserve required product coverage. A reduction does
not require a replacement test for every deleted case. Preserve unrelated work
and historical results, and regenerate inventories only when executable coverage
changes. Follow [failure handling](../../tests/README.md#handling-test-failures)
for an unresolved behavioral failure; this mandate does not authorize deleting
a product assertion merely to obtain a pass.
