# C05u — Prove baseline usability on Ubuntu

Acceptance: installed
Targets: onpc-Ubuntu26.04

Required tasks: C04.
Estimate: 15–30 min for evidence acceptance; 30–60 min if renewal is needed;
session exception: complete baseline customer journey.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and its source, usability, threat and review requirements. Use the affected
design/test owners and source routes below.

## Session boundary and deliverable

Accept the rebuilt Ubuntu candidate before new protection additions against
every assertion in the [finite baseline recipe](../TestAutomation/E2E-Scenario-Recipes.md#c04b-baseline-public-use-slice),
including its separate existing feature and human-pause checks. The
[reuse map](../TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse)
keeps general feature expansion with its E2E owners.

First apply the
[complete baseline evidence-reuse contract](../TestAutomation/E2E-Execution-Contracts.md#complete-baseline-evidence-reuse)
to C04j's retained Ubuntu history and C04's handoff. Record the independent
applicability check and original public results as installed acceptance when
valid. Renew missing, failed, expired or invalidated core evidence through
`tools/run-tests --vm 'onpc-Ubuntu26.04' integration 'check_e2e_baseline_journey'`
with the recipe's original inputs and bounds.
Renew missing or invalidated separate feature/pause slices separately.
Separate prerequisite passes cannot replace the ordered complete journey.

Record desktop gaps for D01/D02 and other ordinary-child route gaps for C06a/C06,
without claiming final confinement.
Repair bounded causes under review/build gates and rerun affected full histories.
Retain exact candidate/selectors/results and complete owned restoration for any
new execution. Report installed acceptance against `onpc-Ubuntu26.04`, citing the
verified complete history and cleanup. Close only C05u when selected; Fedora and
final post-protection acceptance retain their separate gates.
