# Prevent full desktop access through the kiosk account

Task queue: [Ordered task queue](Kiosk-Desktop-Queue.md).
Next task: **D01 — [Review full desktop entry routes](Kiosk-Prompt-Tasks/D01-desktop-review.md)**.
Baseline plan: [Baseline validation](Kiosk-Session-Confinement-Plan.md).
Baseline task: C05f.

## Outcome and scope

Prevent a child from entering a full, unrestricted graphical desktop as the
`oh-no-parent-control` kiosk account. Preserve its passwordless request-only
session, genuine parent approval, time/app enforcement and ordinary-account
desktop access. This is the first security priority after baseline validation.

Own local graphical-session selection, reachable request-session escapes that
yield a full desktop, and one named supported remote-desktop provider. Review
actual child access and the prohibited result before adding a barrier.

Standalone SSH, terminal/TTY access, other exposed actions/consumed inputs and
general confinement compatibility/recovery improvements belong to
[remaining confinement improvements](Kiosk-Session-Confinement-New-Plan.md),
run by `tools/kiosk-prompt-new`. Its C06a requires this plan's accepted D04 gate.
Neither launcher executes or closes the other's tasks. Allocate a cross-boundary
route's desktop-enabling step here and its other results there; reuse shared
mechanisms and exact applicable evidence without duplicate implementation.

## Usability and threat scope

Inherit the baseline's
[usability priority](Kiosk-Session-Confinement-Plan.md#highest-priority-product-usability),
[reasonable-child threat scope](Kiosk-Session-Confinement-Plan.md#mandatory-threat-scope-reasonable-child-effort)
and [selected source boundary](Kiosk-Session-Confinement-Plan.md#target-design).
Every refusal needs actual child access, a deliberate action, the prohibited
desktop result and a working normal-use positive. Trust installed Python/GTK/GI,
native code and normal lazy loading. No private runtime, loader, global inventory
or arbitrary-kiosk-execution premise. Unknown host content cannot veto entry.
Human decisions/authentication are not machine-startup time. Preserve genuine
parent/admin denial, main features and safe recovery from essential outages.

## Task boundaries and size

D01 first verifies accepted C05u/C05f results for both baseline targets, exact
candidate applicability and owned cleanup. Missing evidence keeps D01 open.
New namespaces never bypass an active owner, Git transaction, VM lease or
overlapping uncommitted work.

D01 maps finite desktop routes; D02 independently reviews the minimal design.
C07a owns local graphical desktop barriers and desktop-enabling session escapes;
C07 owns the named remote-desktop route. Existing effective barriers need proof,
not duplicate code. D03 freezes exact finite selectors, inputs, qualifications,
timeouts, normal-use controls and restoration before installed consumers.
C11d/f and C12d/f preserve their stable desktop case identities and targets.
D04 closes only this desktop scope.

Each implementation task owns one reviewed boundary and its directly affected
tests/registration repairs. Ordinary tasks target 20–30 minutes including review
and checks. Local installed tasks retain a 30–60 minute exception for complete
desktop-attempt/core-use/restoration histories. Independent missing implementation
or qualification becomes a bounded prerequisite before its selected consumer
under [ordinary-plan execution](Execution-Plans.md#execution-and-delegation).
Do not absorb a general feature, broker or recovery project into these tasks.

## Acceptance

Require final-candidate public results on both `onpc-Ubuntu26.04` and
`onpc-Fedora44`; this does not broaden release support. Host/review checks and
baseline receipts grant no post-change desktop-defense pass.

| Owner | Required result |
| --- | --- |
| C11d / C12d | Reviewed local graphical-session and request-session desktop attempts fail to yield a full kiosk desktop. Passwordless request-only entry, genuine approval, requested time/soft-app use, continued hard blocks, denial/Cancel without grant, exit/reentry and a fresh request work. Ordinary-account desktop login remains usable. Include affected shared-overlay/feature/pause controls. |
| C11f / C12f | The named supported remote provider admits an ordinary-account desktop and blocks the kiosk-account desktop; normal kiosk entry still works. An absent service or failed positive is no denial pass. |
| D04 | Candidate-matching desktop results, justified refusals, affected regression controls, provenance and owned restoration are inspectable for both targets. |

Use public actions/results for customer acceptance. Engineering probes, root
injections, saved session preferences and an unusable form do not replace that
proof. Reuse only exact applicable candidate, caller, target, provider,
input/assertion and cleanup evidence. Rerun invalidated complete histories after
shared changes. Include directly affected normal-use regression controls without
executing the remaining plan's entire campaign.

## Task execution contract

Apply the [baseline task contract](Kiosk-Session-Confinement-Plan.md#task-execution-contract),
[Approval tools](Approval-Tools.md), [Execution plans](Execution-Plans.md) and
the [test map](TestAutomation/README.md). Read the selected brief and affected
source/callers/contracts. VM/UI/storage mandates apply when triggered. Reuse
qualified mechanics under the
[cross-plan reuse map](TestAutomation/E2E-Building-Blocks.md#cross-plan-baseline-reuse).
New general feature automation remains in the E2E queue.

The coordinator is GPT-6.1 Sol High. Applicable AGENTS.md core-backend model and
independent Astra xHigh review requirements remain binding. D02's independent
design review records explicit Usability priority and Threat scope passed/failed
findings; resolve actionable findings and revalidate material edits.

Retain exact inputs/commands, expected/actual results, blockers, task-owned paths
and cleanup in maintained runner records. Close only the selected row after
review, validation, restoration and launcher Git close-out. Preserve stable IDs,
historical evidence and unrelated work. Build after final packaged-input edits;
product-string changes cover all supported languages.

## Execution

`tools/kiosk-desktop` uses the ordinary shared driver, GPT-6.1 Sol High,
registered VM selection and an independent namespace keyed by this master path.
It inherits task budgets, attachment/stop, guarded recovery and per-task
commit/push. Planning creates no completion or installed pass.

```sh
tools/kiosk-desktop --check
tools/kiosk-desktop --tasks 1
tools/kiosk-desktop --tasks 0
tools/kiosk-desktop --stop
```

These are alternatives. Omitted `--vm` selects configured enabled targets;
installed briefs still require their named target. The existing-grant equivalent
is `tools/execute-plan --plan 'docs/Kiosk-Desktop-Plan.md'`. A new executable joins
the next normal [rules refresh](Approval-Tools.md#one-time-setup); do not refresh
rules or install the product on the development host merely to check this plan.

### Split lifetime

Commit reviewed planning inputs before execution. Preserve all old checkpoints,
accepted evidence, active owners and pending Git work. No checkpoint or handoff
is copied between namespaces. A retained pre-split controller cannot silently
adopt the changed scopes/order. Resolve any retained-state conflict through the
[reconciliation contract](Execution-Plans.md#common-launcher-interface) before
execution; the unchanged-tail split route does not authorize this partial-scope
reallocation. The baseline's original split recovery remains separate and must
retain its committed original destination inputs.
