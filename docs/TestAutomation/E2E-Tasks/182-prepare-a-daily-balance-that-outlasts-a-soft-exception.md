# 182 — Prepare a daily balance that outlasts a soft exception

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW18**. First scheduled consumer: [E2E-038, case 164](../E2E-Scenario-Recipes.md#e2e-038).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065** — FLOW13 grant-only/combined; retained entry and explicit revoke preparation.
- **079b** — FLOW19.
- **047** — APP04 and FLOW08 native usable-app observations.
- **052** — TIME01 public child-desktop remaining balance.
- **052c** — TIME03 bounded real wait.

## Implementation

Compose the exact daily-dominant-with-soft-exception recipe from qualified profiles, app use, retained Parent readback and TIME03. Do not edit allowance or app policy after approval; such edits restore launch blocks.

FLOW18 and its fixed selector have no implementation/registration yet. Add one
shared composition over FLOW13's publicly prepared combined profile,
`real_interval.wait_real_interval`, Parent's public balance read and the
existing native usable/activity helpers. Reuse unchanged grant, app-policy and
retained-entry qualification; qualify only this no-edit-away/wait/return
composition and its D/G inequalities. Invalid profile/owner/deadline refusal
belongs in focused harness checks, with all runtime guards retained. The later
seven cases own their distinct post-expiry actions; do not exercise those
restoration branches while preparing this profile.

## Live VM acceptance

On the live VM follow the recipe's [finite FLOW18 profile and prearmed return](../E2E-Scenario-Recipes.md#expired-grant-with-daily-time-remaining).
Approve the prescribed small addition with soft apps, open S and switch away
while ample grant time remains. Arm the public deadline observer and guarded
return before the final G=60–90-second/D≥120-second Parent witness. Return
directly and independently require D>G>0; FLOW18 must return at that positive
child witness. Qualification may subsequently observe the original grant expiry
on the child desktop; consuming cases own expiry and their post-expiry actions.
Defer settings/form/other-child tours until their owning
post-expiry action. Wrong inequalities fail preparation; no relabeling, top-up
or policy edit after approval. An unreachable real return window stays gated.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_prepare_a_daily_balance_that_outlasts_a_soft_exception
```
