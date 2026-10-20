# R02b — Add the unfamiliar PAM proof fixture

Acceptance: host

Required tasks: R02a — runnable entry/approval transaction.
Estimate: 45–75 minutes; [R01 mechanism estimate](../SystemDesign/Kiosk-Confinement.md#implementation-estimates-after-integrated-review).
Size independent work before execution; this forecast does not expand the session exception or reduce acceptance.

Read the [master early proof](../Kiosk-Resilience-Plan.md#acceptance), accepted
[PAM decision](../SystemDesign/Kiosk-Confinement.md#r01b-effective-authentication-decision),
[task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [shared support guide](../../tests/support/README.md).

## Session boundary and deliverable

Extract one administrator-owned unfamiliar benign PAM session integration from
R02. Use maintained fixture/preparation ownership and complete affected PAM,
ordinary-role and station callers. Specify its finite input and automatic
session effect, an ordinary-account control proving it is effective, and a kiosk
control requiring usable entry plus genuine approval. Use the selected
policy-neutral projection with native control-flow/handle-data equivalence,
without a fixture/module-name exception. Policy-relevant optional-only
success/denial controls retain native execution/results. The
[integrated proof](../SystemDesign/Kiosk-Confinement.md#finite-early-proof-and-implementation-limits)
distinguishes trusted vendor policy helpers from confined kiosk descendants;
no child-reachable unconfined launch effect may pass. R02c owns host-service activation.

## Acceptance and close-out

Host-check installation/verification mechanics, callable composition, ordinary
and kiosk observations, exact restoration and interrupted cleanup under resource/
storage contracts. Reusable installed fixture inputs belong to maintained baseline
preparation; live attempts only verify them. Record existing selectors only once
registered, with engineering limits for R02/R03/R04. No VM run or public acceptance
belongs here. Apply master review/build/localization gates if product inputs
change; complete owned cleanup and preserve existing evidence.
