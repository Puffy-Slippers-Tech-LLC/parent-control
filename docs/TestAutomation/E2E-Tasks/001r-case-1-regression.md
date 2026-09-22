# 001r — Requalify retained case 1

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 1; complete graphical/serial recipe and capture/return reconciliation**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003a** — GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs.
- **003ab** — GDM01/02/08/09 product-free Parent list, prompt and return binding.

## Read only this context

Read only E2E-001 in the [recipes](../E2E-Scenario-Recipes.md#e2e-001), case 1's inventory variant, [controller_qualification.py](../../../tests/e2e/controller_qualification.py) and its actual graphical/serial workers.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the retained case to the qualified public GDM observations and existing authenticated serial transport. Preserve its actual command output, session/boot identity, logout-before-return and capture assertions. Replace a retired generic return binding with the already-qualified public GDM operation; do not invent a graphical VT6 login or use serial proof to authorize graphical secrets.

## Live VM acceptance

The return operations now call the qualified semantic account observation.
The 633 focused accessible-UI, GDM/serial worker and controller reconciliation
checks passed. The [complete attempt](../Evidence/test-all-runs/20260922T153110Z-ef1d0c40/report.md)
failed at its first `gdm-list`: `ui:gdm-account-cardinality`, because the
installed binding requires the station absent on the product-free baseline.
Owned cleanup passed; no scenario acceptance or coverage refresh is claimed.
Private diagnostic: `/tmp/onpc-graphical-smoke-x__r1r2n/private/command-0034-stderr.txt`.
Blocker: product-free GDM binding is unqualified; resume when: task 003ab passes.
Then rerun the complete case below, preserving every serial and capture check.

Run the exact complete case, including all serial and graphical results, independent observations, capture reconciliation, collection and cleanup. A slice or source review cannot satisfy it. Refresh coverage immediately after the successful case.

Run the complete registered case separately:

```sh
tools/run-tests e2e --id '1'
tools/generate_test_coverage.sh
```

Preserve its finite inputs, every recipe assertion, public results, capture
reconciliation and owned cleanup. Regenerate coverage after this successful
case; registration alone is not acceptance.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the proven callable/scope and existing artifact pointer, check
**001r** after its acceptance and cleanup, and advance the master's sole
pointer to the following unchecked row. An unmet requirement keeps this task
current. Delete this brief after enduring context is in the catalogue/source.
