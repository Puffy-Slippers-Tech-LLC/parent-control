# 077b — Search the public app catalogue

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **PARENT10 exact catalogue search results**. Named consumer: task **077** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **010** — UI17 Parent Screen time limit binding; installed qualification and owned cleanup passed.
- **035p** — FIX04 finite native assets and launchers in baseline, with guarded SSH verification.
- **009** — UI16.
- **077a** — PARENT12; UI13 complete public app-row observations.

## Implementation

Reuse PARENT12/UI13 and the installed native fixture identities. Bind public search with exact bounded results and explicit empty expectations.

Use [the finite native declaration](../E2E-Building-Blocks.md#native-fixture-preparation),
`tests/fixtures/native_assets.py`, `native_fixtures.fixture_actions()` and
`native_fixtures.check_catalogue()`. Each owned attempt verifies the accepted
baseline's fixture files before opening Parent; it never installs or repairs them
and never relies on the preceding qualification's VM state.

## Live VM acceptance

Search the prepared fixture name and a declared absent name, independently compare complete public rows and read the fixture's access/match values. Qualify independent App Limits entry and wrong-child/incomplete-result refusal.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_catalogue_search
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
