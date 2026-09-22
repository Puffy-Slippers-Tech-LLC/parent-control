# 001r — Requalify retained case 1

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **Retained regression 1; complete graphical/serial recipe and capture/return reconciliation**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003a** — GDM01/02 ordinary prompt entry; GDM03/04/08/09 recipient, refusal and Escape-return proofs.

## Read only this context

Read only E2E-001 in the [recipes](../E2E-Scenario-Recipes.md#e2e-001), case 1's inventory variant, [controller_qualification.py](../../../tests/e2e/controller_qualification.py) and its actual graphical/serial workers.
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.

## Implementation

Bind the retained case to the qualified public GDM observations and existing authenticated serial transport. Preserve its actual command output, session/boot identity, logout-before-return and capture assertions. Replace a retired generic return binding with the already-qualified public GDM operation; do not invent a graphical VT6 login or use serial proof to authorize graphical secrets.

## Live VM acceptance

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
