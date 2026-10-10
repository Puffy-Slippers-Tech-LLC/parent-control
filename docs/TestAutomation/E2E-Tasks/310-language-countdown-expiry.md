# 310 — Language changes preserve countdown and natural expiry

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **043c** — Retained child unlock/resume through the correct recipient.
- **051** — Public daily-only time profile with zero grant.
- **052a** — Minute and final-second countdown progression.
- **062** — Actual app use until natural enforced lock.
- **310a** — Child panel language propagation with preserved time and policy.

Estimate: 35–55 minutes.
Session exception: Real countdown intervals, child-session resume and natural exhaustion remain one uninterrupted case with no restored-attempt shortcuts.

## Scope and acceptance

Compose the [fixed panel recipe](../E2E-Scenario-Recipes.md#panel-language-and-expiry-planned-task-310)
in one uninterrupted case with the recipe's publicly prepared 10-minute daily-only allowance
and zero grant. Change Riley's product language English → Hebrew → English
through the overlay, close/reopen it and resume the child session. Observe the
shared saved choice and refreshed countdown language/time,
minute/final-second progression and normal natural expiry locking while using
the declared native app. Compare policy/app limits and public time against
elapsed bounds; language changes must not reset time or grant access. Observe
the lock owning harmless normal input and loss of desktop access through TIME04.
No manual lock may stand in for the natural-expiry result.

## Shared implementation

Reuse 051, TIME01/02/03/04, 310a, native activity and retained-session operations. The case owns the finite starting allowance, sample schedule, tolerances and terminal public assertions.

## Implementation entry

One planned complete case; no numeric coverage ID or executable is registered.
Allocate one stable scenario/coverage binding for the linked recipe before
implementation. Run that exact case through the maintained E2E launcher and
regenerate coverage at close-out. Prerequisite qualification is not case acceptance.
