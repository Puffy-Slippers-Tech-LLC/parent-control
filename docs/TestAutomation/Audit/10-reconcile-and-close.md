# 10 — Reconcile audit scope and final verification evidence

**Recommended model: GPT-6 Astra. Effort: high.** The final review must reconcile
cross-layer identity claims, retained behavioral coverage and external blockers.

**Prerequisite:** [07](07-focused-unit-verification.md),
[08](08-host-ui-verification.md) and [09](09-child-static-runtime.md) results
recorded, with no unsafe unresolved route. Apply [shared preflight](README.md).
**Status:** Not started. **Next:** Return to the existing customer queue with
explicit provider/installed qualification blockers; do not execute it here.

## Reconcile current contracts

Review task 02's complete inventory and each implementation disposition. Require
every callable path to use scoped public IDs or refuse before prohibited
discovery/input. Pending scenario status, unit doubles and historical passing
runs cannot establish compliance or live qualification. Preserve all displaced
behavioral assertions and mechanical install/upgrade/migration/removal checks.

Update only affected current contracts, particularly
[Frontends](../../SystemDesign/Frontends.md),
[tests README](../../../tests/README.md),
[building blocks](../E2E-Building-Blocks.md), and current E2E queue/briefs if their
readiness claims conflict with the completed audit. Preserve delivered scope in
historical checked queue rows while explicitly marking their current identity
qualification limitations. Keep provider gaps separate from owned-product gaps
and installed fixture/App Limits qualification. Do not create incident reports,
redefine customer scenarios or mark installed scenarios complete from host tests.

## Regenerate and validate

With no suite active or unread, run:

```sh
tools/generate_test_coverage.sh
jq empty 'tests/e2e/scenarios.json'
git diff --check
git diff --cached --check
```

Run these sequentially and inspect every result. The generator is test collection
and inventory generation, not executed coverage; inspect its output and resulting
`docs/Test-Coverage.md` diff. Its established read-only system listing is permitted
here, but no installed-system test or VM operation is. If it fails, keep the
failure visible instead of manually manufacturing counts.

Discover changed Markdown from HEAD plus untracked files:

```sh
git diff --name-only HEAD -- '*.md'
git status --short
```

Validate **all** existing changed Markdown and every new audit brief, not only
documents edited in this last session. Pass literal filenames in bounded batches
to `tools/read-only links`. The previous 26-document result is historical; the
actual current set is authoritative. The checker validates local destinations,
not anchors or external URLs: review changed anchors manually. Fix links without
altering unrelated staged content, and repeat checks for documents edited after
their validation.

## Close-out criteria

Report separately:

- Owned product/fixture identity work and remaining callable-path count from the
  frozen task-02 inventory. There must be no unassigned or unsafe path.
- Final focused-unit, full twelve-file host UI, child-node, static and applicable
  fixture-runtime results, tied to the final code. No missing final counts may
  be invented or inferred from collection.
- External provider consumers still blocked, their missing actual ID mappings
  and return checks; installed App Limits/package/confinement work still pending.
- Coverage inventory generation, JSON, local Markdown links and both diff-check
  results; staged/unstaged preservation relative to this session's baseline.

Update this queue's current statuses and next pointer. Use **Host remediation
verified; external qualification blocked** when appropriate, rather than an
unqualified claim that all UI automation or customer acceptance is complete.
If required applicable verification is blocked or failed, keep that item open.
Leave runner evidence intact and the checkout unstaged by this session. End with
the next bounded task, recommended model and effort; do not begin VM/E2E work.
