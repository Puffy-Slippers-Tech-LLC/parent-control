# 005a — Start a graphical journey before product installation

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **Product-free graphical start and verified package staging**. First scheduled consumer: [E2E-002, case 2](../E2E-Scenario-Recipes.md#e2e-002).
Read the named [block contracts](../E2E-Building-Blocks.md#refactoring-the-established-cases) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **001** — FILE01, FILE02, FILE06.
- **004** — UI19/GDM05 distinct single-use authentication challenges.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Reuse the accepted product-free baseline and FIX04 transfer. Extend the existing declared setup mode so this journey starts without InstalledSetup installing or rebooting the product. Retain input digests, ownership, capture sealing, phase timing and cleanup. Qualify GDM07 and FILE01 on that baseline; no product installation happens in this slice.

## Live VM acceptance

Start a fresh guarded VM attempt from the accepted product-free baseline, authenticate the intended administrator through two fresh recipient proofs, launch Terminal and observe its usable nonsecret input. Verify the setup-mode/ownership refusals in isolated regressions before the live run. Do not use a maintenance reset as a customer step.

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
