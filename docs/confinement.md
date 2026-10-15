# Kiosk confinement: execution plan

Start each new session with:

> Implement the next task in docs/confinement.md

The reserved kiosk account may run only the product's kiosk session and explicitly
required services. It must never gain arbitrary execution or a normal desktop,
including through another graphical session, terminal or SSH login. Confinement
remains unfinished; completion establishes its tested boundary, not full product
release acceptance.

Task queue: [Ordered task queue](Confinement-Task-Queue.md).

Next task: **4-5d — [PAM and confinement-record ownership refusal](Confinement-Tasks/4-5d.md)**.

Phase 3's isolation exit gate is complete. Phase 4 remains open: latest-version
activation/reboot and removal/reinstall/purge/retry must preserve execution and
admission barriers and account ownership on both targets; final security review,
affected regressions and every required acceptance gap must pass before closure.
The queue preserves completed task identities and evidence. Remaining shared
goals cover Ubuntu and Fedora together; distro-specific recovery stays explicit.

## Requirements
- Drive subagents (stick to 6.1-sol of variant efforts) as needed to divide and conquer especially with lower-tier agent on routine monitoring and coverage refreshes
- Before writing code, have full understanding of existing relevant code
- No hacky code allowed. Must write lean code with supported APIs
- DO NOT ask for approval. Must use established auto approvals.
- Probe live VM for troubleshooting, use live VM to validate fixes before full e2e tests

## Execute the selected task

Apply the [shared execution-plan workflow](Execution-Plans.md), repository
[AGENTS.md](../AGENTS.md) and [approval contract](Approval-Tools.md).
Read the first unchecked active queue row, its brief and only the applicable
references. The queue ends at **Deferred future work**; deferred work is never
selected. Do not skip a blocker or treat planning, preparation, partial evidence
or documentation reconciliation as completion.

The confinement coordinator uses **gpt-6.1-sol xhigh** by default, fixed with
no escalation path. Existing write-e2e and fix-tests model ladders remain with
their launchers.

The public launcher is:

```sh
tools/confinement
tools/confinement --tasks '3'
tools/confinement --vm 'onpc-Ubuntu26.04,onpc-Fedora44'
tools/confinement --stop
tools/confinement --check
```

`--tasks` defaults to one accepted task; values at or below zero select all
remaining active tasks. An oversized limit warns and ends naturally at the queue
boundary. `--vm` supplies a selector under the VM mandate without reducing the
brief's target acceptance. `--stop` requests a safe session boundary; `--check`
is read-only. After accepted work and owned cleanup, the launcher stages only
literal paths belonging to that task, commits and pushes the accepted changes,
including queue/pointer maintenance, before starting another task. Preserve
unrelated working-tree changes.

Legacy prompts **execute next step in confinement.md** and **execute next Phase
in confinement.md** select the same first unchecked task, including acceptance,
owned cleanup and close-out. Default execution completes one task, then stops.

## Scope and acceptance

The [scope and review baseline](Confinement-Reference.md#scope-and-review-baseline)
owns the five confinement work groups and closure assertions. Review includes
the original partial fix `3e0f2af6f9c49e9da0df816f08f39b5c2a2b56fc`
against `697a4c30`, and every subsequent tracked or untracked confinement
change. Do not replace that review with a latest-commit diff.

Product expectations remain in the [specification](Specification.md);
[Lifecycle](SystemDesign/Lifecycle.md) and
[Package removal](SystemDesign/Package-Removal.md) own implementation boundaries.
General reminder, Wellbeing feature, Parent/overlay, multilingual and full
saved-data migration qualification remain with their existing owners and the
[E2E execution plan](TestAutomation/E2E-Execution-Plan.md). This queue changes
neither that plan's next task nor its completion states.

Phase 4 uses only the latest version, without predecessor upgrade assets.
An app-snapshot restore cannot replace a fresh-install/reboot transition.
The removal selector owns one continuous five-phase reboot history per distro;
never split its phases into independent apparent passes. Preserve every assertion
of a shared selector, including ordinary-user controls, while avoiding unrelated
feature implementation prerequisites.

Use the [validation allocation and evidence ledger](Confinement-Reference.md#validation-allocation-and-evidence-ledger)
before selecting tests. Remaining recovery tasks add focused installed histories;
they do not automatically rerun the full removal history or Phase 3 public kiosk
cases. Task 4-5b established the first focused controller route; later recovery
tasks extend it. Keep the existing full removal regression intact.
Final task 4-10 owns broad final confinement qualification and required invalidated
histories; task-local affected validation remains mandatory before close-out.

For shared remaining goals, implement common mechanics once and qualify Ubuntu
and Fedora concurrently through the [maintained VM scheduler](Mandates/VM-Mandate.MD#target-selection)
within its configured cap. Keep one editor for shared code under the
[delegation contract](Execution-Plans.md#execution-and-delegation), separate
per-target inputs/evidence/cleanup and ordered histories within each VM. Both
targets must pass before accepting the task; a shared fix requires affected
qualification on both. Preserve the [serial Preferences qualification route](Confinement-Reference.md#step-7b-qualification--2026-10-13)
until concurrent execution is qualified. Keep indivisible recovery chains together.

Successful allowed controls must precede execution/admission denials; require
independent enforcing-boundary observations. Missing coverage, unavailable
evidence, setup failure or an inconclusive negative stays open. Required
in-scope gaps and unaccepted limits block closure. Product mismatches follow
[test failure handling](../tests/README.md#handling-test-failures).

## Load only the selected context

| Need | Read |
| --- | --- |
| Component and trust boundaries | [System design module map](System-Design.md#find-the-relevant-design), then the affected module. |
| Selected scope and acceptance | First unchecked queue row and its brief; required rows describe delivered scope, not cached readiness. |
| Native boundaries and source files | Relevant [technical boundaries](Confinement-Reference.md#technical-boundaries) and complete affected functions/callers/callees. |
| Missing lifecycle assertions | [Coverage audit](Confinement-Reference.md#phase-4-step-1--coverage-and-verified-inputs--2026-10-13). |
| Historical inputs and results | Only the applicable [qualification evidence](Confinement-Reference.md#qualification-and-reusable-evidence) section. |
| Test allocation, reuse and required reruns | [Validation allocation and evidence ledger](Confinement-Reference.md#validation-allocation-and-evidence-ledger), then only the affected evidence rows. |
| Registered selectors and installation mechanics | [Installed runner](../tests/integration/README.md#running-the-current-installed-suite), launcher help/listings and the selected brief's routes. |
| Independent security review | [Review checklist](Confinement-Reference.md#primary-source-routes-and-independent-review-checklist) and original baseline. |
| VM, UI or storage work | Applicable [VM](Mandates/VM-Mandate.MD), [UI automation](Mandates/UI-Automation-Mandate.MD) or [storage](Mandates/Test-Storage-Mandate.md) mandate. |

Links are reading routes, not instructions to load the full reference or every
brief. Broaden reads when ambiguity, changed shared state or failure requires it.

## Completion and evidence

Use exact package/source/helper/fixture/baseline identities and verify retained
reports before reuse. Requalify affected or unproven histories after changes;
checked historical rows do not silently qualify a later candidate. The
[retention gate](Confinement-Reference.md#phase-4-step-1--coverage-and-verified-inputs--2026-10-13)
requires exported raw results before journal rotation and rechecking exports after
later exports. Missing required evidence requires repeating the affected complete
history. Never read online snapshot `snapshot.json` credentials.

Update the ledger at each accepted task with exact applicability, retained raw
evidence and required follow-ups. A new chat, documentation close-out or unchanged
candidate is not itself a reason to rerun a valid attempt. Export sessions also
rotate: check the required evidence set against both execution and export budgets
before starting more runs; a collection of remembered export paths is insufficient.

Run scoped affected host checks, and `make build` after the final package-affecting
edit. Preparation and host checks supply no installed/customer acceptance.
Use registered targets only; never install the product on this development host
or return to the released incident machine.

If work is substantial, split only unfinished tasks before execution, preserving
their numbering, dependencies, continuous histories and every assertion. Record
`Blocker: …; resume when: …` for incomplete acceptance, leaving its row and
pointer unchanged. After successful acceptance and owned cleanup, preserve useful
evidence once in the reference, check only the accepted task, remove its temporary
brief, and advance the pointer to the next unchecked active row. Reconcile the
Phase 4 exit gate only after every in-scope obligation passes.
