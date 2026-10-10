# 184 — Create the registered spare child through shared account helpers

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ACCOUNT01/02 shared account read/create; AUTH04 protected-account guards**.

Required tasks: none (Baseline). AUTH04 qualifies this operation's fixture/SSH
authority and protected-account guards; no graphical authentication is involved.

## Read only this context

Read ACCOUNT01/02 and AUTH04, [account_fixture.py](../../../tests/e2e/account_fixture.py), and the existing fixture account/credential ownership and cleanup tests.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Extend the shared account-fixture helper to create the registered disposable standard child through supported system commands or AccountsService over guarded SSH. Read back its exact account/role. Keep credential bytes on the existing sealed provisioning channel; reject collisions and protect the active/last administrator and station. Validate known controller, registered-account and ownership restrictions before command submission; no desktop accessibility discovery is needed. No Users page, Unlock prompt or add-user wizard.

## Live VM acceptance

Create the registered spare in a fresh owned attempt and independently verify its role. Wrong identity, collision, unauthorized source and replay refuse without changing protected accounts. Require cleanup. Retain this preparation for the remaining account-removal and role-change consumers. Completed [case 3](../E2E-Building-Blocks.md#parent-discovery-block-contracts) owns live discovery, selection and settings checks with Parent open; system readback cannot pass that app assertion.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_create_disposable_child
```

Use the shared watch intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.
