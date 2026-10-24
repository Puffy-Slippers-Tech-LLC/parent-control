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
- **Maintain existing critical infrastructure coverage.** Protect
  runner selection/verdict integrity, credential boundaries and guards against
  destructive or unauthorized actions on accounts, processes, files or VMs.
  Exercise these shared boundaries directly with minimal controlled inputs.
  This is not a requirement to unit-test infrastructure features or tools.

Being located under `tests/` or `tools/` neither requires nor exempts coverage.
The behavior and consequence of failure determine the need. A shared helper
implementing a core guarantee belongs to core infrastructure; an ordinary case
helper, test data builder or assertion wrapper does not become core merely
because other tests use it.

**By default, no new unit tests for non-product code, unless specifically asked for.**
Change and run non-product code through its existing consumers; if it breaks,
fix it in use. This default includes infrastructure, launchers, qualification
scripts and reusable helpers, even when they implement a critical guarantee.
Maintain existing coverage without automatically adding cases or suites.
Apply this rule to new implementation, automated repair and every task brief
or launcher. A specific request for non-product unit tests permits them within
the requested scope, subject to the proportionality and duplication limits below.

Classify the specific behavior being tested, not the importance of the tool
containing it. A failure that makes ordinary development work unavailable,
incorrect, inconvenient or slower does not by itself justify new unit tests. Shared
use, dependency status and guards that stop work do not establish criticality.
Critical infrastructure coverage protects a direct failure path to a false
execution/verdict claim, credential exposure, or a concrete dangerous or unauthorized action;
hypothetical downstream effects and general reliability claims are insufficient.

Here, false-pass protection means execution integrity: selected work actually
runs, failures/skips/missing results cannot become a pass, and evidence belongs
to that attempt. It does not mean separately unit-testing every scenario's
assertions, expected values, observations or sequence with synthetic product
results. Those are ordinary test code; validate them through their product tests.

Do not add dedicated unit-test suites for ordinary development aids unless
specifically asked for. Examples include their presentation, convenience and
orchestration features: VM test video recording, watchers/viewers, scenario
composition, qualification wrappers, assertion helpers and fixture data builders.
Use them in their normal workflow. Complexity, reuse or a bug in such a tool
does not by itself warrant another test layer. Shared credential and destructive
operation guards remain tested once at their existing owner, rather than through
every tool that calls them.

Do not add assertions, parameters, fixtures or cases for non-product behavior to
an existing unit suite without a specific request. An existing test owner
does not grant broader coverage scope. Adapt existing tests only as necessary
to preserve an admitted guarantee when its implementation or interface changes;
validate ordinary feature behavior through its normal consumers or a bounded
smoke run instead.

## Limits

- Do not automatically add tests for test cases, assertions, doubles, private
  fixtures or helpers. Verify ordinary test changes by running the affected
  tests. Add a separate non-product unit regression only when specifically asked
  for and existing coverage does not already protect the behavior. Stop there;
  that regression creates no obligation for another layer of tests around it.
- Keep at most one dedicated test layer around a core infrastructure guarantee.
  Test its real implementation with small controlled inputs; do not add tests of
  that regression, its doubles, assertions or private setup. A small synthetic
  passing/failing test is appropriate when checking a runner's actual verdict;
  replaying real feature-test bodies or recursively launching their suites is not.
  A separate integration check is warranted only for a distinct process,
  privilege or storage boundary that the direct check cannot exercise.
- Do not add or retain UI tests of test tools, including dashboards, watchers,
  evidence viewers and fixture control panels. Exercise any critical execution,
  input-safety or destructive-cleanup guarantee beneath their UI.
  Product UI tests may use graphical fixtures and automation; the tool's own
  widgets, navigation, rendering and presentation are not acceptance targets.
- Reuse existing coverage before adding a case. Use representative inputs and
  meaningful failure boundaries; add combinations only for distinct interacting
  behavior. Do not mirror each implementation branch, function, helper or
  consumer with a separate test, duplicate a shared guarantee in every case,
  or add tests solely to increase counts or coverage percentages.
- A new scenario, wrapper, selector, stage, diagnostic value or consumer must
  not automatically expand a shared infrastructure test matrix. Check shared
  dispatch, fail-stop, ownership and decoding behavior once with representative
  inputs. Keep a finite registration/selection check where omission could cause
  a false pass; do not execute the full safety matrix for every registered item.
  For independent dimensions, vary one at a time from a valid baseline. Cross
  dimensions only when their interaction can change the protected result, and
  explain that interaction in the normal change description. Do not enumerate
  an implementation's generated vocabulary as a substitute for testing its rule.
- Keep validation proportional to the change. Run the smallest affected
  selection through maintained launchers. Do not run tests of the runner as a
  prerequisite to ordinary product tests or repeatedly requalify unchanged
  infrastructure. Documentation-only policy edits need document checks, not
  new tests asserting the policy's wording.

## Review and reduction

For each proposed test, identify the product outcome or specifically requested
non-product behavior it protects, the distinct failure it detects and why
existing coverage is insufficient. Keep this explanation in the normal change description when
needed; do not create a separate checklist, evidence file or test for it.
If no concrete gap exists, do not add the test.

For specifically requested non-product unit coverage, identify any existing test
owner before adding another case or module. Review the fully expanded parameter
count, not just the number of test functions. Prefer extending or replacing the owner's
representative check over copying it into a new consumer-specific module.
Keep the tests within the specific request; a bug fix alone does not authorize
new non-product unit coverage. Automated implementation and repair must apply
this default too. Do not build another checker, registry or test suite to enforce
this mandate.

This default does not require removing existing non-product unit tests. Remove
test-tool UI tests and redundant recursive checks rather than moving their entire
matrices to another layer. Preserve any unique core guarantee with the smallest
effective direct check; preserve required product coverage. A reduction does
not require a replacement test for every deleted case. Preserve unrelated work
and historical results, and regenerate inventories only when executable coverage
changes. Follow [failure handling](../../tests/README.md#handling-test-failures)
for an unresolved behavioral failure; this mandate does not authorize deleting
a product assertion merely to obtain a pass.
