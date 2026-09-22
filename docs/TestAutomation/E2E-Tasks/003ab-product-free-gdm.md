# 003ab — Qualify product-free GDM navigation

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **GDM01/02/08/09 product-free Parent list, prompt and return binding**.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **003a** — GDM01/02 prepared ordinary prompt entry; GDM03/04/08/09 Parent/other-parent recipient, refusal and Escape-return proofs.

## Read only this context

Read the GDM01/02/08/09 rows and case-1 stage contract in the
[catalogue](../E2E-Building-Blocks.md#case-1-stage-contract),
`AccessibleUI.gdm_semantic_rows`, its account/navigation/prompt callers,
`onpc_gdm` and the existing guarded GDM qualification envelope.
Read the affected accessible-UI and qualification cleanup tests.

## Implementation

Case 1's declared product-free baseline has prepared ordinary accounts but no
product station. The installed adapter currently requires Parent and station
for every list observation. Add an explicit product-free binding for the named
case-1 consumer, retaining the installed binding's station cardinality checks.
Declare the expected fixture identities before observation; never choose the
profile by accepting whichever tree appears. Preserve complete snapshots,
ownership, duplicate rejection, password/list exclusion, fresh focus and
single-use input guards. Do not install the product or fabricate a station to
make the product-free harness pass. No graphical secret is authorized.

Reuse the existing public semantic adapter and guarded qualification envelope.
Implement the fixed argument-free `check_e2e_gdm_product_free` integration
selector with applicable cleanup coverage before invoking it. This is a new
fixture binding, not a new generic selector or VM runner.

## Live VM acceptance

On a fresh accepted product-free baseline with declared ordinary fixtures,
observe the Parent row, focus and verify it, press Enter once, independently
observe the Parent password prompt, press Escape once and observe the returned
list. Repeat from independent valid list entry. Prove list observation refuses
the observed prompt before Escape. Preserve owner, ambiguity, incomplete-tree,
stale-focus and uncertain-input regressions, including installed station checks.
Use shared watchvm intent/display/transport and require collection and owned
cleanup. Record the actual provider version, locale and keyboard tuple.

Run isolated affected cleanup checks, then:

```sh
tools/run-tests integration check_e2e_gdm_product_free
```

The complete serial/graphical case remains task 001r immediately afterward;
this slice supplies no complete-scenario acceptance credit.

## Close out

Update the catalogue with the exact qualified product-free callable and route.
Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup),
then advance to 001r and delete this brief. Keep installed bindings and pending
desktop/secret routes distinct. If qualification fails, preserve its normal
runner artifacts and exact return condition.
