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

Create the registered spare in a fresh owned attempt and independently verify
its role. Focused harness checks cover wrong identity, collision, unauthorized
source and replay before command submission, with discovery unavailable and no
protected-account mutation. Require cleanup. Reuse this operation for later
consumers; no account state survives between their attempts. Completed
[case 3](../E2E-Building-Blocks.md#parent-discovery-block-contracts) owns live
discovery, selection and settings checks with Parent open; system readback cannot
pass that app assertion.

Source gap: `DynamicAccountFixture.create` delegates a fixed standard-account
creation to `e2e_dynamic_account.create`; it exposes no general registered
read/create/remove/role operation. Extend those shared owners with the declared
spare registry and independently observed result, preserving their single-use
run/transport guards. Do not describe the later remove/role selectors as ready.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_create_disposable_child
```
