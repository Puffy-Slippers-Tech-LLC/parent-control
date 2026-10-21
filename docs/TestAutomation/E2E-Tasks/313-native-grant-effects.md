# 313 — Qualify shared native grant, use and revocation effects

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 30–60 minutes.
Session exception: one uninterrupted grant, app-use and revocation history with public restoration per target.
Targets: `onpc-Ubuntu26.04`, `onpc-Fedora44`.

## Scope and prerequisites

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **313a** — Compatible finite native fixture profile and shared bindings.
- **180** — Public zero-daily Parent setup and saved balance readback.
- **079** — Shared public app match/access editing.
- **047** — Native usable-app Submit/result operations.
- **050** — Public revocation/Confirm and saved balances.
- **052** — Public child countdown comparison.
- **043c** — Retained-child time restriction and safe greeter return.
- **044b** — Retained Parent entry and activity identity.

Own the general feature automation previously requested by kiosk C04p. First
consumer: that baseline validation task. Later 065a, 079b/079d and 197/197a/197k
reuse this exact delivered scope under the
[cross-plan map](../E2E-Building-Blocks.md#cross-plan-baseline-reuse); they retain
their additional arguments, entry modes, results and qualification.

## Implementation and acceptance

Preserve the existing in-progress `tests/e2e/baseline_app_effects.py`,
`check_e2e_baseline_app_effects.py` and `onpc_baseline_app_effects.pm` work and
the [retained failure](../../Kiosk-Prompt-Tasks/C04p-app-effects.md#retained-work-and-return-condition).
Names need not change with queue ownership. Inspect complete shared policy,
fixture, native-launch, request-flow, recipient and comparison functions first.
After 313a, extend only missing finite shared bindings; no second policy,
authentication, instance or denial implementation belongs in this qualifier.

Use the [finite native history](../E2E-Scenario-Recipes.md#baseline-inputs-and-public-results):
Riley/Jamie, zero daily/grant, Allowed A, precise permanent H and version-pattern
conditional S; public Custom 10 Minutes/600 seconds, soft included. Read saved
rules; genuinely approve once; independently read positive grant-only time with
elapsed bounds; use distinct A-primary/S-secondary windows through Submit/result;
observe attributed H command denial. Close S before A, return to retained Parent
with positive grant, revoke/Confirm, read zero grant and unchanged saved rules,
then observe the same child's time restriction and attributed S command denial.
Restore H/S to Allowed and disable Riley's controls publicly before outer cleanup.

Run affected host composition/refusal, fixture/renderer and shared comparison
checks with explicit timeouts. Inspect registration and current per-VM inputs,
then use the existing selector:

```sh
tools/run-tests --vm 'onpc-Ubuntu26.04,onpc-Fedora44' integration 'check_e2e_baseline_app_effects'
```

Keep independent 1800-second attempts and original observation/input-freshness
bounds. No synthetic grant, clock changes, missing-window denial or daily-only
expiry substitution. Retain exact candidate/fixtures/providers, public outcomes,
collection and owned restoration. No installed pass exists yet. Update only the
qualified finite scope and later briefs' remaining work; close no kiosk row,
broader FLOW13/19/20 capability or complete E2E scenario automatically.

The compatible fixture implementation and host checks are now delivered in the
[C04p1 handoff](../E2E-Building-Blocks.md#c04p1-compatible-fixture-applicability).
Use its full Versioned S target/wildcard and current fixture-source-keyed inputs.
Older ten/seven-file receipts do not verify the expanded twelve/nine-file
native/Riley profile; verify maintained baseline preparation before installed
attempts. Both-target installed grant/use/revocation acceptance is still pending.
