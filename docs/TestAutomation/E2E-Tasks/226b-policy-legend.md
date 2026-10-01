# 226b — Read the public app policy legend

Use the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver UI04/UI03 public App Limits legend expansion and semantic readback for
Jordan, including all three access rules and precise/pattern matching.
First scheduled consumer:
[E2E-041, case 184](../E2E-Scenario-Recipes.md#e2e-041).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **077** — Jordan-bound catalogue search/filter operations and exact row reads.
- **226a** — Fresh Jordan allowance setup for this consumer's declared entry.

## Implementation

Read the [E2E-041 recipe](../E2E-Scenario-Recipes.md#e2e-041),
[catalogue filters](../E2E-Building-Blocks.md#catalogue-filters) and the
UI03/UI04 catalogue rows. Inspect `parent_page`, `app_rows` and public-ID
input/read helpers in `tests/e2e/accessible_ui.py`, operation dispatch/schema
in `tests/e2e/ui_observations.py`, and
`tests/integration/graphical_smoke/lib/onpc_app_rows.pm`.
The product's `_legend_card` / `_legend_section` in
`parent/oh_no_parent_control_parent/main.py` own the content and expose
`parent-legend-toggle` / `parent-legend-content`; locate the actual symbols
before editing. The existing wrong-control toggle refusal is not a legend read.

The qualified Jordan allowance entry is `fresh_thirty_allowance.JORDAN_PLAN`
with `FreshThirtyAllowanceJourney` and `onpc_parent::set_allowance`'s explicit
`gdm/parent/fresh/new/existing/0/30/1` binding. Reuse those shared setup and
balance operations with caller-owned stages, not the qualification lifecycle.

Use owned public IDs to open the legend, then independently read its complete
access and matching explanations. Bind Jordan and App Limits before input;
refuse wrong child/page, missing or duplicate IDs, wrong owner and incomplete
content. Names/text may verify meaning after ID resolution. Keep immutable
initial/final complete rows and compare unchanged access/match choices.
Qualify an independently open legend without replaying expansion. Put reusable
mechanics and bounded result validation in shared libraries, with caller-owned
invocation stages. Preserve the existing catalogue qualification lifecycle.
Cover actual worker order/refusal stops, realistic observation decoding and real
recorder startup/comparison before live execution.

## Live VM acceptance

The implemented selector uses `policy_legend.PLAN` / `PolicyLegendJourney`,
`PolicyLegendQualification` and `onpc_app_rows::policy_legend`. Shared
`AccessibleUI.expand_policy_legend` / `read_policy_legend` and
`onpc_app_rows::legend` own the guarded expansion/read, with caller-owned stages.
The qualification reuses Jordan's shared fresh allowance and balance operations,
retains immutable complete rows, and independently reads an already open legend.
Host guard, worker order/refusal, response-decoder and real recorder/comparison
coverage lives in `test_e2e_app_rows.py` and
`test_installed_journey_cleanup_safety.py`; the real GTK read is
`test_preview_smoke.py::test_public_policy_legend_full_read_and_unchanged_choices`.
Installed qualification remains required:

```sh
tools/run-tests integration check_e2e_policy_legend
```

Require full explanations, independent entry/readback, wrong-entry refusal,
unchanged policies, collection and owned cleanup. Run affected catalogue/toggle
regressions through their existing selectors:

```sh
tools/run-tests integration check_e2e_catalogue
tools/run-tests integration check_e2e_toggle
```

This slice grants no complete-case acceptance credit; case 184 stays separate.

## Current failure and remaining work

Implementation and host validation passed, including shared guard/refusal and
worker-order checks, real controller decoding, recorder startup/comparison and
the complete real GTK legend read with unchanged policies. The preview exposed
GTK's omitted collapsed Revealer subtree; expansion now guards the toggle first
and the independent expanded read requires the content ID and full explanations.
The existing wrong-control toggle refusal remains unchanged.

The first live `check_e2e_policy_legend` run failed at `legend-expanded` after
fresh Jordan setup/balances, complete initial rows, wrong-child/page refusals and
independent App Limits entry passed. No expansion result, independent legend
read or final row comparison passed. The catalogue/toggle live regressions have
not run. Leave diagnosis and correction to the next session; no live retry or
failure repair occurred here.

Evidence: `output/test-runs/host/reports/20261001T050542Z-92ea21ab/report.md`,
adjacent `category-001.log` / `failure.json`, and
`output/test-runs/privileged/allocations/onpc-graphical-smoke-ngxugkm_`
(`legend-expanded.request.json`, `result.json`, `private/`, `worker-private.log`).
The runner reported `e2e:worker-execution-failed`, followed by
`command:failed:ssh`; cause remains uninvestigated. Worker/display cleanup and
baseline restoration completed; collection/finalization details remain in the
retained result. The enabled-VM queue drained and exited with failure.

Host evidence: `output/test-runs/host/reports/20261001T050014Z-0751bc62/report.md`
(1479 safety/unit checks), `20261001T050306Z-460dcc2c/report.md` under the same
reports root (177 updated adapter checks plus real GTK preview), and
`20261001T050349Z-fd5dac9c/report.md` (301 composition/consistency/scheduling
checks). Product/build inputs are unchanged; no package build was required by
the test-only edits. The live launcher built and verified its missing named
qualification inputs automatically.
