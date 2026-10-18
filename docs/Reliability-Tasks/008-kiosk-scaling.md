# 008 — Kiosk startup and exit under inventory growth

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

[Task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract)
and [system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance).
Estimate: 60–90 minutes.

## Session boundary

Deliver the paired ordinary/enlarged inventory measurements and independent
functional/resource results. 008a supplies locale/Request ordering, including
the agent-locale failure slice formerly in 009; 008b supplies logout fallback.
Session exception: all eight samples on each target must compare the same
candidate and fixture profiles. Do not split cold/warm or ordinary/enlarged
samples into independently accepted tasks or drop a failed intermediate result.

## Purpose and route

Required tasks: 006, 007, 008a, 008b.
Read the [master](../Reliability-Plan.md),
[frontend lifecycle](../SystemDesign/Frontends.md),
[timing measurement contract](../../tests/e2e/README.md#kiosk-transition-timing),
existing `vm_probe.py` timing functions, `KioskLogout`, agent-locale preparation,
artwork loading and native namespace staging/cleanup.

Planned qualification (unimplemented): `check_e2e_kiosk_inventory_scaling`,
extending the existing timing qualification/transport owner. Diagnostic probes
alone supply measurements, not this task's installed functional acceptance.

## Finite measurements and expected results

Compare the same verified candidate with ordinary inventory and 256 additional
inert, root-owned sibling entries supplied through owned fixtures. For each
profile take one explicit cold-boot sample and three warm entry/Request/Cancel
samples: eight samples per target. Record the exact ordinary inventory identity
and added-entry manifest. Within each sample observe a ready usable form,
submit Request once, observe one correctly bound approval prompt, cancel that
prompt without a password, confirm unchanged choices and grant/policy, then
use station Cancel and independently observe usable GDM.

Retain each raw entry-to-form, Request-to-observed-prompt and station
Cancel-to-usable-greeter interval. Preserve the existing transport/observer
overhead definitions, guest read costs, clock-offset bounds and the distinction
between semantic observation and presented/painted witnesses. Compare ordinary
versus enlarged inventory separately for cold and warm samples of this same
candidate. No older-package comparison, percentile or trimmed ten-trial mean
is implied. Existing operation deadlines and functional outcomes are the pass
oracles; report latency deltas and unresolved measurement uncertainty without
inventing a performance threshold or replacing usable results with paint.

Submit each Request at the first independently established form readiness;
do not deliberately wait for speculative locale warm-up to finish. Deterministic
host callback/job tests from 008a cover Request during pending warm-up, required
preparation ordering and stale-language refusal; incidental fast completion on
a VM must not become a timing-race prerequisite or a claimed pending-warmup pass.
Compare quiescent checkpoints after every sample: no extra hidden-session
clients, preparation timers or duplicate staging mount trees may remain beyond
the same roles' recorded idle baseline and explicit owned resources. Do not use
global process counts as that oracle.

Reproduce latency defects at the responsible stage and fix redundant work or
protocol/lifecycle mistakes without weakening policy, durability, recipient
checks or deadlines. Preserve bounded logout fallback when native services fail.

## Work sequence

1. Verify one candidate and both exact inventory manifests before collecting
   samples. Establish each profile's recorded idle resource baseline.
2. Collect the ordinary profile's cold sample and three warm samples. In every
   sample finish the declared ready-form, prompt/Cancel, unchanged-state and
   usable-GDM observations before the next sample.
3. Collect the enlarged profile's cold sample and three warm samples with the
   same functional/resource observations. Retain every raw interval and failed
   intermediate result; all eight samples remain one acceptance set per target.
4. Compare cold pairs and warm groups, reporting latency deltas and uncertainty
   under existing deadlines. Restore the owned inventory and finish cleanup.

## Validation and close-out

Run affected host rendering/cache, agent-locale/logout, namespace and timing
ownership checks. Perform the finite qualification on both targets, retain raw
samples, functional outcomes and complete cleanup. Document material remaining
latency and its stage; an average improvement cannot conceal a failed transition.
Build after product edits and retain actual selector bindings in existing owners.
Reuse 008a/008b's host coverage; add only new defect regressions. The full paired
measurement set must match final inputs after any product or fixture repair.
