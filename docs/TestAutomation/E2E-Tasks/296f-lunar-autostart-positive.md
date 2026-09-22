# 296f — Observe allowed Lunar autostart across login

Estimate: 40–60 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

Session exception: Continuous pre-login observation touches shared recorder/secret handling and requires the retained live regression set.

## Scope and prerequisites

Deliver **APP06/UI22 allowed continuous login interval**. Named consumer: task **296b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **296a** — APP01/02/03 and UI18 Minecraft local-world binding.
- **007** — LIFE02.
- **016a** — UI22.
- **004** — UI19/GDM05 distinct single-use authentication challenges.
- **052c** — TIME03.
- **180** — FLOW01 same-user entry; FLOW16 fresh/same Parent allowance setup.

## Read only this context

Read only the delivered block rows and their named callables in the
[catalogue](../E2E-Building-Blocks.md), the selected consumer's recipe clauses,
and the affected safety/adapter tests. Follow the
[scoped reading rules](../E2E-Execution-Plan.md#load-only-the-selected-context).
Use delivered prerequisite scopes; do not open predecessor briefs.

## Implementation

Compose existing Lunar/tray/game readers with the shared login observer. Arm before child login input and preserve sealed capture, reattachment and all samples through 90 seconds after desktop readiness.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Observe working allowed autostart continuously from before login submission. Require the actual tray/Lunar result and reject blind intervals, ambiguous ownership and missing samples. Retain all applicable recorder/secret/cleanup regressions.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_lunar_autostart_positive
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **296f**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
