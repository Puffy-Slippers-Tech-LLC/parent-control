# 005 — Qualify terminal administrator password input

Estimate: 40–60 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **AUTH03; FILE06 package challenge/completion**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#kiosk-child-overlay-and-the-shared-request-form), [related block contracts](../E2E-Building-Blocks.md#customer-terminal-files-and-application-use) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **005a** — Product-free graphical start and verified package staging.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind one declared installation command and selected administrator to the real non-echoing terminal challenge. Extend FILE06 to observe that challenge, then implement AUTH03's independent recipient qualification. Reuse applicable safety machinery; a generic Password string is insufficient. Qualification submits the command with FILE02, qualifies the challenge twice, types UI19 once and submits with UI05; LIFE04 is composed only afterward.

## Live VM acceptance

On the VM, reach a real package-command challenge, refuse wrong-account/wrong-recipient evidence, obtain two fresh intended proofs and type the fixture secret once. Captures and outputs remain secret-safe; completion is independently read.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_install
```

This selector must exist under the master's [qualification contract](../E2E-Execution-Plan.md#live-verification-contract)
before invocation. Require every stated result, independent valid entry, wrong-entry
refusal and owned cleanup on the live VM. Host tests and a diagnostic slice do not
establish complete scenario coverage.

## Close out

After live qualification and cleanup, update the callable, exact qualified scope
and status in [E2E-Building-Blocks.md](../E2E-Building-Blocks.md), and reconcile
the first consumer's status in [E2E-Scenario-Recipes.md](../E2E-Scenario-Recipes.md).
A slice alone leaves the full scenario pending. If any complete E2E scenario
passed, run `tools/generate_test_coverage.sh` after that case's cleanup; it runs
`tools/generate_test_coverage.py`. Require successful generation before check-off.

Check this task in the [master](../E2E-Execution-Plan.md), then remove this brief
when its enduring context is in source/contracts and replace its master link
with plain text. Validate changed Markdown with `tools/read-only links`.
Keep normal runner artifacts; no new evidence document or accumulated history.
