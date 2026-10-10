# 123a — Save a match draft after fixture removal

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–50 minutes.

Session exception: The retained editor, actual removal, catalogue absence, reinstall and restored-rule observations form one continuous qualification.

## Scope and prerequisites

Deliver **LIFE04 fixture remove/reinstall; PARENT15 retained-editor save; PARENT02 catalogue refresh**. First scheduled consumer: [E2E-020, case 111](../E2E-Scenario-Recipes.md#e2e-020).
Read the named [block contracts](../E2E-Building-Blocks.md#time-and-ordinary-lifecycle-boundaries), [related block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **079** — PARENT16 and FLOW03 public app-policy editing.
- **006** — LIFE04 install only.

## Implementation

Bind verified fixture removal/reinstallation commands. Save the real open draft with PARENT15 while Parent still holds its pre-removal row. Select Riley and back to Jordan through PARENT02 in the same Parent window, await the loaded catalogue and observe the app's absence. Reinstall and use the same refresh before checking the retained rule; no removed-app row is expected in a freshly loaded catalogue.

Register the exact fixture package identity and supported remove/reinstall
commands through the shared `PackageCommand` transport. Existing
`package_install.submit_install/submit_release` are product-package bindings,
and native baseline files are not this package lifecycle. Reuse the same
PARENT15 and shared PARENT02 refresh composition as update; the new qualification
owns only disappearance/reinstallation and retained-rule readback. Missing
verified fixture package inputs remain a concrete prerequisite, not permission
to substitute private catalogue removal or recreate product installation tests.

## Live VM acceptance

On the live VM, leave a nondefault match draft open, remove the fixture through the shared administrator SSH package helper and Save through that same owned editor's Application UI API operation. Select Riley and back to Jordan through PARENT02 in the same window and observe exclusion from the loaded public catalogue. Reinstall through the shared administrator SSH package helper, repeat that refresh and independently read the retained rule before editing it. No Parent restart, supporting window or desktop switch is needed.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_catalog_removal
```
