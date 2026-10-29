# 035b — Qualify versioned AppImage pattern assets

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX06 versioned-path readiness; FILE05 and finite Allowed launch bindings**. First scheduled consumer: [E2E-041, case 189](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079d** — APP02 and FLOW08 native blocked-launch results.

## Implementation

Bind the current/next matching versions and existing/new nonmatches from the
maintained deterministic AppImage-path fixture assets for case 189. Declare
reusable sources in baseline preparation and verify through FIX06. Prepare the
recipe's copies through FILE05; no vendor download, updater or AppImageLauncher setup is
needed for this pattern test. Reuse command-result projections. Case 189 owns
the wildcard Save, matching/nonmatching policy effects, refresh wait and
rejected-save recovery; do not repeat them as readiness qualification.
Case 253 separately owns the real Lunar integration.

Source boundary: `_build_native_layout` builds the next S version, but
`native_assets.sources()`/baseline verification declare only the current four
executables. Bind that existing next-version asset and the exact new nonmatch
to a finite FILE05 profile; do not rebuild vendor assets. Extend the current
primary-only `AccessibleUI.native_launch_command` and result projection for
matching/nonmatching identities. Reuse the installed system native-policy
owner's backend wildcard/future-version/UID checks rather than another matrix.

Reuse `native_assets.py`'s existing `Applications/Versioned` directory and
`version_pattern`, with the GUI runtime already supplied by `baseline_assets.py`.
Declare only missing next-version/nonmatch sources in that finite profile;
do not move the fixture or build another directory preparation framework.
Keep representable nonmatches distinct from the recipe's deliberately unsafe
pattern. Its rejection and preservation of the prior confirmed rule stay in
case 189, alongside the successful pattern/enforcement branch.

## Live VM acceptance

Verify the finite source identities through FIX06, add the declared files
through shared FILE05 and independently observe their copy results. Qualify
one usable Allowed launch/result for each newly supported executable binding.
Reuse unchanged input/ownership guards and independent entry; no denial,
60-second refresh or rejected-pattern history belongs to this asset slice.
Those customer results remain pending in case 189.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_qualify_versioned_appimage_pattern_assets
```
