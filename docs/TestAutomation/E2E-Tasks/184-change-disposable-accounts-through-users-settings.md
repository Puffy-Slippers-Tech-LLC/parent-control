# 184 — Add a disposable child through Users settings

Estimate: 30–50 minutes for a focused implementation/validation cycle; not
a stop timer. Follow the [master session contract](../E2E-Execution-Plan.md#execute-one-task).

## Scope and prerequisites

Deliver **ACCOUNT02 add-child; AUTH04 account-creation password fields**. First scheduled consumer: [E2E-040, case 179](../E2E-Scenario-Recipes.md#e2e-040).
Read the named [block contracts](../E2E-Building-Blocks.md#additional-public-surfaces) and only the selected consumer's recipe.

Required implemented capabilities (IDs identify master rows; no predecessor brief is needed):

- **184a** — AUTH04 Users Unlock; ACCOUNT01.
- **009** — UI16.

Use the catalogue's maintained callables and a fresh attempt, never prior task/VM state.

## Implementation

Bind the finite add-child wizard and its standard-user role. Nonsecret fields use UI16/UI15; each creation password field gets two fresh AUTH04 proofs and one UI19 input. Refuse unregistered identities before input. Preserve the active administrator and station.

## Live VM acceptance

On the live VM, add one registered spare standard child through Users and independently read its resulting row/list. Qualify creation-secret recipient checks before input. In a separate attempt, cancel the wizard and require the original list unchanged. Parent discovery is checked by the complete scenario.

Run affected safety/adapter checks, then use the complete first consumer if runnable.
Otherwise implement/reuse the planned fixed qualification:

```sh
tools/run-tests integration check_e2e_change_disposable_accounts_through_users_settings
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
