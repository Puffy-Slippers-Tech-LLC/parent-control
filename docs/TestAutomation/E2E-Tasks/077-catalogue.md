# 077 — Filter the public app catalogue

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Session boundary

Add both access and match filter popovers with their option sets. Reuse 077b's search/result observations; keep exact zero-result assertions.

Reuse the delivered scope of tasks **077b** under the
[split-task contract](../E2E-Execution-Contracts.md#task-size-and-order).

## Scope and prerequisites

Deliver **PARENT10, PARENT11**. First scheduled consumer: [E2E-041, case 184](../E2E-Scenario-Recipes.md#e2e-041).
Read the named [block contracts](../E2E-Building-Blocks.md#app-grid-search-and-parent-launch) and only the selected consumer's recipe.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **035p** — native baseline assets and launchers; guarded read-only verification.
- **009** — UI16.
- **077a** — PARENT12; UI13 complete public app-row observations.
- **077b** — PARENT10 exact catalogue search results.

## Implementation

Own the complete UI preview matrix: five queries × four match subsets × eight
access subsets from the recipe, including zero results and unchanged policies.
Keep finite values and exact comparisons shared with the installed sample.

Reuse PARENT12 and the complete app-row reader. Start at the delivered
[catalogue search](../E2E-Building-Blocks.md#catalogue-search):
`onpc_app_rows::search`, `AccessibleUI.CATALOGUE_ROW_OPERATIONS`,
`native_fixtures.fixture_actions()` / `search_rows()` and the finite text bindings.
Bind the prepared native profile to Jordan through explicit `existing` text
child bindings and `existing-parent-app-rows`; unprefixed row bindings target Riley.
Extend search bindings for the recipe's description/identifier matrix and add
both access/match filter popovers using UI17. Empty expected results are explicit;
search reads no installed catalogue backend. Compose shared leaves with a new
caller-owned plan, rather than inheriting the search qualification's lifecycle.

## Live VM acceptance

On installed Parent, search one prepared native app, select a combined precise
and Allowed filter, then clear. Observe the exact real catalogue rows and unchanged
policy. Preserve independent-entry and wrong-entry refusal qualification; the full
query/filter cross-product runs in UI tests.

Qualification composition: `CatalogueJourney` in
[`catalogue.py`](../../../tests/e2e/catalogue.py) owns a fresh plan;
`onpc_app_rows::filter` supplies reusable option setting and checked closure.
`AccessibleUI.catalogue_filter` binds both public option sets to explicit child
entry, and `native_fixtures.catalogue_rows` shares the finite exact oracle with
`test_catalogue_complete_query_match_access_matrix`. Description and identifier
queries use the same text input/readback as the installed name sample.

Qualification selector (implemented and registered; live acceptance pending):

```sh
tools/run-tests integration check_e2e_catalogue
```
