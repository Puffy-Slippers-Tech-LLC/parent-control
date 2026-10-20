# R01d — Settle configuration and quarantine ownership

Acceptance: review

Required tasks: R01b — effective administrator policy; R01d0 — accepted evidence recovery.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[configuration target](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary and route

Extract pre-GDM account setup from R01. Read complete
`packaging/lifecycle/postinst.in` and `tools/provision.py` provisioning,
`accounts_service_provision_kiosk()`, `accounts_service_set_icon_file()`,
`repair_kiosk_visibility()` and cache-version/transaction/expiry callers. Trace
failure and retry through actual public visibility and quarantine release.
Runtime/broker readiness and update activation belong to R01e.

## Deliverable and acceptance

Choose narrowly verified capability/schema behavior or a public visibility-repair
route, preserving unrelated account fields and ordinary users. An unfamiliar
compatible version is not a veto; an unknown schema must not be written blindly.
Separate optional icon assignment from required enforcement/setup; its fallback
uses the display default without needing another successful icon API call.

Define transaction/field ownership for temporary quarantine, captured prior
expiry, interruption and later administrator denial. Resolve the same-value
administrator-write ambiguity: equality with the saved expiry alone proves no
ownership. Require bounded product recovery without overriding effective policy.
Assign visibility implementation to R05a, quarantine to R05b and icon degradation
to R08a. Add each real pre-GDM rejection to the single ledger with controls,
sanitized cause and exhausted safe-recovery alternatives. R01 reviews the
integrated mechanism; this task implements nothing. Check changed links and
documentation consistency; preserve existing evidence and no runtime resources.

## Current handoff

The [selected decision](../SystemDesign/Lifecycle.md#r01d-configuration-and-quarantine-decision),
single rejection ledger and R05a/R05b/R08a briefs are reviewed. Independent Sol High
review findings were resolved: early setup-only gate bootstrap, native creation's
partial-publication window, absent-only completion under the native account lock,
staged-home ownership, present credential/expiry preservation, legacy reconciliation
and policy denial after ready publication. No runtime implementation or installed
acceptance is claimed; R01 still owns integrated architecture review.

[590 selected checks](../../output/test-runs/host/exports/onpc-evidence-bundle-c9764iq7/evidence.zip)
and [313 close-out consistency checks](../../output/test-runs/host/exports/onpc-evidence-bundle-c9764iq7/evidence.zip)
passed; changed design/consumer links passed (193 destinations). Full queue link
validation found four pre-existing missing destinations in R01a/R01b/R01c:
`cde3e0fe572f4020b716ba82062769da/agent-result.json` and three links to
`34c21acf65cf4f69be0b6f50e343a52f/agent-commands.log`, under the existing
`output/test-runs/host/plans/eef8d83fd673614a6f0e83adad07b9c3981f98c1618cb827f4a2bf6bd84b72a2/`
namespace. These allocations are no longer retained.

The retained R01c recovery checkpoint
`3211116e00164fb584fd3fb4a1bb0998/checkpoint.json` establishes accepted completion
and cleanup, but does not retain the detailed checks behind those four labels.
Verified bundle `onpc-evidence-bundle-z93cqybl/evidence.zip` contains only the
R01c reports `20261020T055104Z-8b6c8f9c` and `20261020T055213Z-ae99f789`;
the two cumulative baseline bundles predate these predecessor records. Do not
substitute newer R01d checks or that checkpoint for the missing exact proof.

That checkpoint retains the earlier developer answer authorizing automatic
documentation reconciliation and a root-cause repair, so no repeated developer
permission request is needed. The [execution-plan contract](../Execution-Plans.md#plan-format)
permits only verified destination-only predecessor repairs during ordinary
close-out; changing the historical labels/claims needs the controller's reviewed
reconciliation route. Controller work must preserve earlier completion/scope,
disclose unavailable detailed evidence accurately and prevent evidence retention
from expiring still-referenced accepted results. Do not recreate expired reports
or manually edit saved checkpoints. Resume R01d close-out after that boundary is
resolved, rerun the affected links/consistency checks and only then check this row,
remove this brief and advance to R01e.

The source review on resumption confirmed that `Plan.validate_recovery()` and
`Plan.validate_transition()` permit destination-only completed-row changes;
`reconcile_plan()` requires an inactive controller and committed planning files.
This task may neither commit those files nor start another workflow launcher.
The [explicit prerequisite](../Kiosk-Prompt-Queue.md) now owns the authorized
evidence-lifecycle repair and controller reconciliation. R01d remains unchecked,
with unchanged scope and review acceptance, suspended behind that prerequisite.
Preserve all earlier completion, exact scope and valid retained evidence. Resume
the remaining link/consistency acceptance after R01d0, without treating its host
checks as R01d acceptance or as replacement proof for the missing old checks.

Before another host test run, preserve the two R01d reports through maintained
storage. The finished `retention-host/current.json` currently records them as
its two history entries, followed by current report
`20261020T145951Z-1b24bc2f`; a new session would retire the 590-check report.
This resumption therefore checked the new brief/consumer/master links without
starting another retention-mutating test run. R01d0 owns preservation before
fresh consistency validation, not reconstruction after that proof expires.

Prerequisite-insertion validation: eight design/consumer/master/brief documents
passed 210 local destinations. Including the queue checked 274 destinations and
found exactly the same four missing predecessor references (queue lines 10–12).
`git diff --check` passed. Direct queue/guard review confirmed the one unchecked
prerequisite sits immediately before R01d, requires completed R01c, and is added
to R01d's existing R01b dependency; all existing completion, relative order,
scope and other dependencies are unchanged. Fresh host consistency execution is
deferred for the preservation reason above. No subagent started successfully;
the agent inventory contains only the coordinator. No runtime cleanup remains.

All subagents finished. Both maintained test runs ended successfully; no VM,
product process or temporary runtime resource was created or remains owned.
Only documentation changed, outside packaged/build inputs; no build is required.
No staging, commit, push or second workflow launcher was performed. Continue with
GPT-6.1 Sol High and reuse the reviewed design and valid scoped checks.

R01d0 preserved these reports in the linked cumulative bundle before host
rotation. Their original members are `20261020T145235Z-f4caa62b/report.md` and
`20261020T145335Z-6bf77d40/report.md` under the checkout's host report root;
the bundle also retains their full command/results/input records. Read them
through the maintained bundle reader. This changes only their location, not
their original result, inputs or applicability.

R01d0 close-out: the fresh controller applied the reviewed historical disclosures
and report relocations. The corrected queue and saved active/suspended state
agree; full queue links and required consistency checks pass. Resume this task's
remaining review close-out with the preserved decision and reports. R01d remains
unchecked; R01d0 supplies no review acceptance or missing historical check result.
