# 035b — Qualify versioned AppImage pattern assets

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX04 AppImage versions; FILE05 and pattern launch results**. First scheduled consumer: [E2E-041, case 189](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#fixture-boundaries-and-the-common-attempt-envelope), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **186** — PARENT15 failed-save; FEED15 Parent and report-close binding.
- **052c** — TIME03.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the current/next matching versions and existing/new nonmatches from the
maintained deterministic AppImage-path fixture assets for case 189. Prepare
copies through FILE05; no vendor download, updater or AppImageLauncher setup is
needed for this pattern test. Reuse saved same-directory wildcard rules and
command-result projections. Register the finite read-only refresh wait without
retrying launch input. Case 253 separately owns the real Lunar integration.

## Live VM acceptance

On the live VM, add the next version through shared FILE05 copy commands, require matching versions denied and existing nonmatches usable. For the new nonmatch, wait at most the recipe's 60 seconds and issue one declared launch. A rejected pattern must expose its report and preserve the prior confirmed rule.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_qualify_versioned_appimage_pattern_assets
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
