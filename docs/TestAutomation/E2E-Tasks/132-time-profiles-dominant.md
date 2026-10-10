# 132 — Compose a daily-dominant profile without clearing the grant

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FLOW13 daily-dominant scope**. First scheduled consumer: [E2E-024, case 128](../E2E-Scenario-Recipes.md#e2e-024).
Read the named [block contracts](../E2E-Building-Blocks.md#reusable-journey-fragments) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **065a** — FLOW13 grant-only profile and explicit revoke preparation.

## Implementation

Extend FLOW13 with real short grant at daily=0, then increase daily allowance while Screen time limit stays enabled. Supply earlier observations and verify D>G>0 at both Parent and the later request estimate.

Build this branch directly from 065a's grant-only operation and the shared
PARENT06/PARENT08 enabled allowance edit. Do not replay the independent
grant-dominant/combined qualification. The inequality checks belong to this
new composition and use the prior public balance endpoints, not an additional
unchanged read. Preserve the two different observations at Parent and request
time because elapsed use can reverse the intended dominance.

Keep the finite consumer profiles distinct: case 128 uses the ordinary
2-minute grant then daily 6; cases 227/228 use their delayed-approval table's
4-minute grant then daily 10 and the larger dominance margin. Parameterize only
these declared shared inputs, retaining each caller's public inequality and
elapsed-time comparison. The current fixed 75-second request composition and
0/15/30 `configure_time_controls` binding do not implement these values.

## Live VM acceptance

On the live VM preserve a real G while raising D through Parent, then read D>G>0 again at request time with elapsed/rounding margins. A reversed inequality fails; never relabel the variant.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_time_profiles_dominant
```
