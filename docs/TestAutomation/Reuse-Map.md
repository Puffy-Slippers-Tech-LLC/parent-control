# Reuse for customer scenarios and package qualification

The [master checklist](Test-Automation.md#unfinished-tasks) owns order;
[Continuation.md](Continuation.md) selects the next complete customer variant.
Read only the relevant row and existing interface. The
[surface-only contract](E2E-Coverage.md) applies across every customer family;
the timeout/login example is not a special focus.

## Customer scenario work

| Consumer | Reuse | Acceptance boundary |
| --- | --- | --- |
| 21A/21B Parent | Accepted GDM/app input, account fixtures and installed setup; shared request helper only when needed. | Visible discovery, controls, save, access, app use and revocation. No broker/catalog/policy witnesses. |
| 22A/22B time | Real Parent/request actions, normal login/switch/unlock and bounded screen matching. | Display, natural expiry, rejection and later legitimate access. No PAM, usage/grant or session probes. |
| 23A/23B overlay | Installed shared form, real system prompt and secret-safe input. | Visible choices, approval/cancel/retry, countdown and actual app use. |
| 24A/24B kiosk | Same shared form/input plus real GDM entry/return. | Request-only interaction, selection, approval, exits and observed cross-surface persistence. No agent-stop test. |
| 25A/25B app use | Prepared native/Snap/Flatpak assets, customer launch routes and normal user switching. | App windows/denials and another user's continued use. No execution probes or process/rule inspection. |
| 26A/26B recovery | Existing customer close/reopen, cancel/retry, logout/login/reboot/suspend actions. | Visible recovery and resumed use. No induced daemon or transaction faults. |
| 26C complete journeys | Compose the same customer interactions with prepared real game/attachment assets. | Continuous gameplay, requests, expiry and authorized feedback response. Fragments are not a complete journey. |

A missing helper must name an actual blocked customer step and finish with that
consumer. Do not requalify all lower-level helpers, expand backend coverage or
reopen the deferred policy design before writing the next customer scenario.

## Existing interfaces to find once

- [Guarded graphical input, recording and safe artifacts](../../tests/e2e/README.md).
  The current runtime contract still has legacy backend requirements: reconcile
  the first affected consumer and minimum validator under E2E-Coverage.md.
  Keep existing provenance, secret handling, VM ownership and cleanup.
- [Installed runner and package/account setup](../../tests/integration/README.md).
  Its verified setup is usable without full Task 20 acceptance.
- [Existing fixture/artifact contract](../../tests/integration/README.md#package-and-fixture-inputs).
  Reuse assets; bring forward missing real-game/Snap assets only with their case.
- [Shared test support](../../tests/support/README.md).
  Existing unit/component/system regressions remain unchanged. Use established
  imports and cleanup safeguards; they do not become customer assertions.
- [Retained engineering interfaces](Engineering-Reuse.md#existing-interfaces-to-find-once)
  are for scoped mechanical/engineering work, not E2E startup context.

### Qualified GDM and serial helpers

Reuse [accepted 19B qualification](Evidence/19B-Acceptance-20260908.md) and the
[retained interface details](Engineering-Reuse.md#qualified-gdm-and-serial-helpers).
E2E-001 remains one harness smoke, with no customer completion credit. Repeat
qualification only for relevant changes or a demonstrated consumer failure.

### Installation helper and open limits

Mechanical Tasks 18/20 retain
[installation contracts and historical limits](Engineering-Reuse.md#installation-helper-and-open-limits)
and [Task 20 recovery/checkpoints](Task-20.md#bounded-recovery--2026-09-11).
Their internal startup, ownership, integrity and cleanup checks remain required.
A feature journey uses accepted setup; only a demonstrated shared-helper blocker
justifies bringing forward the minimum repair, with actual R1 costs retained.

## Installed and runner work

- Tasks 18/20 remain active mechanical package work after the customer queue.
- Tasks 15–17 remain separate unaccepted engineering. Preserve their existing
  tests and [retained qualification](Engineering-Reuse.md#installed-and-runner-work).
- [Policy acknowledgement](Policy-Acknowledgement.md) is explicitly deferred and
  is not a dependency of customer launch, login, save or request scenarios.
- General Tasks 27/28A expansion is deferred. Only a concrete blocked consumer
  may require a minimal safe adapter; no new reporting or orchestration framework.

## Graphical work

Use [the customer rows above](#customer-scenario-work) and the finite scenario
table in [E2E-Coverage.md](E2E-Coverage.md#enumerate-scenarios-before-implementing-them).
Do not follow the former graphical rows in Engineering-Reuse.md as current
instructions: they retain superseded backend witnesses and fault matrices.

## Evidence and final acceptance

Reuse current safe screen/step reports and cleanup outcomes. Customer acceptance
requires no internal product evidence. Package/system evidence keeps its own
contract. The [progress workflow](Implementation-Workflow.md#handoff-format-and-cost-review)
tracks complete customer variants, frozen remaining scope and separate scope
transfers; unit counts and qualification passes do not stand in for journeys.

## Resolve before the affected batch

- Reconcile legacy mandatory backend/other-user product assertions with the
  first affected customer consumer; preserve safety metadata and exact failures.
- E2E-003's new-account action is declared supported fixture setup followed by
  visible discovery. E2E-005's save outcomes belong to 21B.
- Reclassify backend-induced E2E-028/029 and transport faults explicitly. Task 20
  keeps its startup-fault qualification; other unfinished internal work is
  separate. No reclassification earns a completed customer scenario.
- E2E-026/027 customer lifecycle paths and internal package checks are separately
  labeled under Tasks 18A/18C. No double counting of shared complete journeys.
- Real-game/app assets and external sending authorization block only their
  affected cases. Complete independent customer work while they remain blocked.
- This documentation change marks no runtime variant ready or passed. Keep
  actual executable status truthful until implementation and execution.
