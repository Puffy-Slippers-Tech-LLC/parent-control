# 184 — Create the registered spare child through shared account helpers

Estimate: 20–30 minutes. Follow the
[session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **ACCOUNT01/02 shared account read/create; AUTH04 protected-account guards**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **004** — UI19/GDM05 distinct single-use authentication challenges.

## Read only this context

Read ACCOUNT01/02 and AUTH04, [account_fixture.py](../../../tests/e2e/account_fixture.py), and the existing fixture account/credential ownership and cleanup tests.
Apply the [system-operation rule](../../Mandates/UI-Automation-Mandate.MD).

## Implementation

Extend the shared account-fixture helper to create the registered disposable standard child through supported system commands or AccountsService over guarded SSH. Read back its exact account/role. Keep credential bytes on the existing sealed provisioning channel; reject collisions and protect the active/last administrator and station. No Users page, Unlock prompt or add-user wizard.

## Live VM acceptance

Create the registered spare in a fresh owned attempt and independently verify its role. Wrong identity, collision, unauthorized source and replay refuse without changing protected accounts. Require cleanup. Complete case 179 separately observes Parent's live discovery; system readback cannot pass that app assertion.

Implement and register this planned fixed qualification and its cleanup coverage before invoking it:

```sh
tools/run-tests integration check_e2e_create_disposable_child
```

Use the shared watchvm intent, display and guarded command transport. Pass
applicable cleanup/ownership checks in isolation first. Require independent
result readback, sanitized evidence and owned cleanup. Host tests alone do not
qualify a live route or complete a customer scenario.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record the proven callable/scope and existing artifact, check **184** only after
acceptance and cleanup, and advance the sole pointer in queue order. Keep an
unmet requirement pending with its return condition. Delete this brief after
its enduring contract is recorded in the catalogue/source.
