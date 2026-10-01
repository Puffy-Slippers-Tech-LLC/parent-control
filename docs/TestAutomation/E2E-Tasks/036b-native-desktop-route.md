# 036b — Observe policy results for desktop launches

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Session boundary

Add desktop-specific blocked results after a public Parent save. Reuse 036g/036h's usable and separate-window bindings; missing DING support remains a blocker.

Tasks **036g**, **036h** supply the extracted operations through their maintained
callables and qualified scope. The delivery below is cumulative with those
prerequisites. Implement only the remaining slice above. Keep the original
acceptance results: reuse valid independent-branch evidence, and run every new
composition and any earlier branch affected by the change. No saved VM state or
predecessor brief is an input to this session.

## Scope and prerequisites

Deliver **APP01/02/03 native desktop route**. First scheduled consumer: [E2E-019, case 68](../E2E-Scenario-Recipes.md#e2e-019).
Read the named [block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035p** — FIX04 native assets; LIFE04 fixture installation.
- **036h** — APP01/02 desktop separate-window route.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse 036g's verified entry and shared command/API placement and trust
preparation. Bind its public desktop activation and independently observe usable
or blocked results. Missing desktop support blocks this route; do not install
another desktop extension or substitute a different launcher.

The installed desktop icon is owned by DING. Reuse 036g/036h's qualified
icon/activation and separate-window bindings with wrong-icon and ambiguous-owner
refusal. This task adds only the policy-result observations; it does not repeat
launcher preparation or add selection/menu permutations. Search, command or
file-manager activation cannot replace the tested desktop route.

## Live VM acceptance

On the live VM, activate the actual desktop entry, observe the real app window and perform a normal usability action. While an earlier S activity remains open, use a supported desktop gesture to launch and independently identify a second window; presenting the first window cannot pass. Apply a public Parent block and observe this route's declared blocked result. Qualify independently reached desktop entry and wrong-target refusal; terminal/file-manager activation is not desktop acceptance.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).
Run the fixed qualification below once implemented and registered:

```sh
tools/run-tests integration check_e2e_native_desktop_route
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
