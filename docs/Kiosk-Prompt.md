# Kiosk entry and unexpected password prompt

Task queue: [Ordered task queue](Kiosk-Prompt-Queue.md).
Next task: **001a — [Audit authentication and account admission](Kiosk-Prompt-Tasks/001a-auth-account-audit.md)**.

## Outcome

Selecting the request station must reach its usable confined form without a
kiosk password. Unrelated installed software must not become a prerequisite for
entry or invalidate a healthy retained station. Genuine authentication-policy,
required-input, ownership or enforcement failures must remain closed and leave
enough sanitized evidence in customer feedback to identify the failed boundary.

Use the shared [execution infrastructure](Execution-Plans.md),
[approval routes](Approval-Tools.md), [test ownership map](TestAutomation/README.md)
and [failure handling](../tests/README.md#handling-test-failures). Product behavior
belongs to [the specification](Specification.md#2-component-specifications) and
[kiosk confinement](SystemDesign/Kiosk-Confinement.md). This plan does not promise
exhaustive protection against every future dependency or weaken an intentional
security refusal to suppress GDM's fallback presentation.

## Symptom boundary and stop condition

This is a kiosk-entry repair plan. Its customer path starts when the dedicated
account is selected at GDM and ends at a usable confined request form, or an
intentional refusal followed by restoration and successful reentry. It covers
the observed ambient-directory rejection, the reviewed alias/name defects,
retained-manager rejection after unrelated filesystem changes, effective
passwordless authentication and diagnostics for these entry failures.

Discovery must account for the existing authentication-to-form failure stages,
but a stage map does not require a new test or redesign for every stage. Reuse
valid existing coverage. Add implementation or installed acceptance only for a
demonstrated cause of this entry symptom, or a direct safety regression risk
introduced by changing that entry mechanism. Every added task must name the
concrete source dependency, finite failing/control condition, exact selector
and affected targets. Unrelated discoveries go to their existing owner and do
not expand this queue or add acceptance gates. Failures in mandatory checks for
changed code still follow their owning failure/acceptance contract.

Required safety controls remain: required-input drift still refuses, omitted
ambient data stays outside the private view, confinement stays enforcing and
ordinary-account authentication/access is unaffected. These are targeted
regression controls for the entry fix. This plan does not qualify child time/app
limits, request approval/revocation, all kiosk escape scenarios, every desktop
service/plugin, all package lifecycle variants or the full feedback UI/transport.
Parent feedback is exercised only to collect and validate entry-failure evidence.
Mandatory checks for code actually changed still follow their owning contracts.

Do not add graphics, geometry, coordinate-based input or coordination-specific
test automation for this work. Reuse existing semantic operations and result
observers. GDM acceptance concerns refused entry, safe session state and usable
reentry after restoration; exact screen appearance, prompt layout and error-message
wording are diagnostic observations, never acceptance assertions or new adapter
prerequisites.

Close the plan when its entry regressions and those direct safety controls pass
on both declared platforms, the original failure remains diagnosable after
recovery, and all owned state is restored. No general product acceptance gate
may be added to that stop condition.

## Incident and initial audit

On 2026-10-18 at approximately 22:07–22:08 local host time, native authentication
explicitly accepted the kiosk's blank password, and account/session routing
passed. Both manager and GDM preparation then failed at `directory-layout` with
`unsafe-directory-entry`. The installed helper matched the checkout before this
work. The unrelated `/usr/share/eusoft-eudic` directory was user-owned, mode 0755.
Commit `83d502b3` had handled root-owned writable directories such as VS Code's,
but left the ownership rejection in place. Source history introduces that check
with the confinement helper in commit `eb0b7323` on 2026-10-12. Neither the v1.0
nor v1.3 tag contains that helper. The observed late-rejection cause is therefore
a compatibility regression from the newer confinement work, retained by the
October 17 partial fix; it is not established as a bug present since v1.0.
This source/history attribution and the actual incident journal do not constitute
a live comparison of the same host configuration against those older releases.

The initial read-only audit found these distinct work items. Task 001 must
verify the complete paths and coverage against the execution checkout.

| Boundary | Evidence and remaining gap | Owner in this queue |
| --- | --- | --- |
| Ambient entries | `directory_layout()` rejected non-root siblings; unrelated files, links, special types, unusual names and metadata races need a generic classification with required-input controls. A candidate is already in the checkout. Required lexical alias ancestors are missing from its required set: a post-inventory non-root symlink parent is omitted as a sibling. Three private review cases reproduced this (`20261019T053221Z-e4ed23a4`); their expected refusal did not occur. A separate private publication probe reproduced `UnicodeEncodeError` for a non-UTF-8 sibling filename (`20261019T053414Z-0ce83392`); include such names through publication, not only tab/newline checks. | 001b, 002a, 003a, 003 |
| Customer evidence | PAM/preparation records previously stayed outside feedback; native bind failures expose only `stage=bind`. A bounded admission-export candidate is already in the checkout. Actual host manager/gate producer metadata matches its reviewed parser. | 002b, 002, 010a, 010 |
| Late denial and greeter | Healthy empty-token PAM and healthy GDM entry do not prove what the user sees after preparation/binding fails, or usable recovery afterward. | 004a, 004 |
| Retained generation | `prepare()` hashes the complete ambient layout. Unrelated additions/removals or kind changes can stale the manager. Removing layout from the digest alone does not safely reuse its pinned mounts. | 005a through 007 |
| Authentication policy | Fedora explicitly refuses `without-nullok`; Ubuntu's module-presence checks do not themselves prove effective empty-token authentication. This is a separate hypothesis, not the observed incident. | 001a, 008a, 008, 009a, 009 |
| Affected existing entry evidence | Review existing account-classification, first-configuration, upgrade or native-update evidence only when a changed entry dependency affects it. A config-drift test named stale-manager reaches attestation first; do not count it as generation-stage proof. No blanket lifecycle campaign is required. | 001, 011a, 011 |

The existing 32,768-entry, four-generation, 512 MiB and preparation-timeout bounds,
required native inputs, lexical aliases, privilege helpers, MAC enforcement,
ownership locks and package quarantine retain their safety contracts. Enlarged
inventory and timing work remains with [Reliability 008](Reliability-Tasks/008-kiosk-scaling.md).
New gaps that pass the symptom-boundary test need finite prerequisite briefs
before their consumers under the shared plan contract. Other discoveries remain
with their existing owners; they do not authorize a release-wide campaign.

## Execution and acceptance

Discovery is the first three bounded tasks: authentication/account admission,
preparation/native confinement, then session/readiness/feedback coverage
reconciliation. Their union must map the shipped entry failure stages and the
finite missing regression controls before implementation closes. Existing
unaffected coverage need not be requalified. The independent review confirmed
the incident's blank authentication followed by preparation refusal; it did not qualify a new native
candidate. The selected existing host checks passed 1,223 cases on 2026-10-19 UTC.
The deliberate alias-ancestor and non-UTF-8 publication failures remain unresolved
engineering evidence in existing runner reports; temporary review probes were
removed.

A further independent review reproduced five host failures in
[the exported probe report](../output/test-runs/host/exports/onpc-artifact-export-tmc1qzhs/report.md):
non-root lexical directory/link ancestry and an intermediate target link were
masked/omitted instead of refused; a non-UTF-8 sibling failed actual binding
publication; and an unrelated masked-directory addition changed the digest and
rejected an otherwise unchanged retained-manager model. The temporary probes
were removed and their containing file restored exactly. These are bounded
engineering reproductions, not maintained regression coverage or installed proof.
The first review report rotated during subsequent checks. The same five failures
were reproduced in run `20261019T061016Z-d39f14ad` and exported before close-out;
the linked report includes their probe source and failures.
002a owns the first four failures; 005a/005 and 006a/006b/006 own retained-view
repair, with installed acceptance at 003/004/007. Required-path completeness and
metadata-race controls remain mandatory within those owners.

A follow-up review retained
[five additional host probe failures](../output/test-runs/host/exports/onpc-artifact-export-3obq7d2l/report.md)
in run `20261019T061847Z-d1c50a84`: non-UTF-8 publication failed for both roles,
ambient addition still changed the retained-manager digest, an absent required
native destination escaped the preserved-only layout completeness check, and
20 repeated denial records displaced all authentication/routing/recovery context
from a 31-record diagnostic input. The last two are newly demonstrated gaps;
002a and 002 respectively own their permanent regressions and correction.
002a also owns the source-reviewed post-layout ambient disappearance/trust-drift
boundary: native bind checks remain strict, but currently make that unrelated
source an entry prerequisite. Its brief requires a bounded prerequisite if
safe handling needs an independent mechanism. These are engineering observations,
not installed acceptance. Temporary probes were removed and both containing
test files restored to their exact pre-probe hashes.

The same review found stale proof allocation: the current account-classification
selector is system case 5, and the config-mutation check in
`verify_execution_boundary()` reaches payload attestation before generation
comparison. The enduring references are corrected; 001b/001 and 011a/011 still
must allocate actual generation-stage, final-candidate receipts, using
`system_native_update.stale_admission()` only where its inputs and evidence match.
011a also owns the finite documentation repair for eight unavailable local
recording links in `Kiosk-Confinement-Proof.md` (lines 33, 39 and 40 at review).
Classify them against the existing accepted retention-loss record; this is no
new removal/lifecycle acceptance gate and does not reopen accepted history alone.

Task sizing separates classification, native diagnostics, report projection,
retained-view primitives, admission integration and final evidence allocation.
Installed rows are split by target; each target retains its whole failure,
restoration, recovery and cleanup history. Original numeric IDs identify the
remaining composition, whose delivered scope includes its extracted prerequisites.
Both targets and all in-scope entry/safety assertions remain required. Later
fixes require review of affected earlier receipts and reruns where their relevant
installed inputs changed, under the owning evidence contract. Record the final
package identity and exact input comparison supporting reuse; a different package
hash alone does not mandate unrelated acceptance histories.
Installed fault/recovery histories have explicit session exceptions;
their estimates are not timers. Independent newly discovered work whose upper
estimate exceeds 30 minutes requires a bounded prerequisite before execution,
not silent expansion of the current row. No task may absorb a release-wide
validation campaign. Existing retained launcher runs, if any, still require the
shared explicit reconciliation route; editing this plan does not alter them.

Run `tools/kiosk-prompt --check` to validate this plan without execution.
`tools/kiosk-prompt --tasks 1` executes the next task; `--tasks 0` executes the
remaining queue. Repeating the command reconnects; `--stop` stops between agent
sessions. The wrapper uses GPT-6.1 Sol High and the existing driver, ownership,
task budgets, Git close-out and VM selection. It adds no separate runner or
approval mechanism. New executable command grants use the existing setup-owned
tool discovery; do not broaden rules to start it.

All rows start unfinished. Current source changes and host passes are candidate
work, not installed acceptance or completed queue tasks. At execution, preserve
pre-existing edits and reconcile their ownership through the shared launcher;
do not overwrite a protected dirty baseline or claim it as a task commit.
The development host's installed product and live sessions are not execution
targets for this plan. Each installed brief declares its target; the queue
covers both registered platforms under the [VM mandate](Mandates/VM-Mandate.MD).
Public observations follow the
[UI mandate](Mandates/UI-Automation-Mandate.MD); fault injection remains engineering
coverage. Store results and perform identity-owned restoration through existing
helpers under the [storage mandate](Mandates/Test-Storage-Mandate.md).

For every installed task, retain the original failure and expected/actual result,
exact candidate/package and fixture identities, enforcing security mode, positive
ordinary-account controls, restoration and owned cleanup. Do not enter a password
into an unexpected kiosk-account prompt. Run only affected existing histories;
host passes, manifest inspection, preparation and a successful retry cannot
replace native isolation or public recovery proof. Build after the final
packaged edit. The final row reconciles evidence against the actual final inputs.

## Coordination with existing plans

This queue owns the new kiosk-prompt work. Reuse canonical confinement,
admission, PAM, account and native-update implementations, rather than create
parallel test mechanics. [Reliability 006a](Reliability-Tasks/006a-sibling-masking.md),
[006b](Reliability-Tasks/006b-required-path-refusal.md) and
[010](Reliability-Tasks/010-diagnostic-recovery.md) retain their independent scope
and unfinished status. Their executors must first inspect this queue's matching
receipts and implement only a remaining gap. Each launcher closes only its own
reviewed row; shared evidence must match its full scope, targets, candidate and
cleanup. Do not run overlapping implementations concurrently or edit another
workflow's retained checkpoint.
