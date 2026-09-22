# 001ta — Submit one nonsecret terminal command and read help

Estimate: 20–30 minutes. Aim for one session; this is not a stop timer.
Follow the [session contract](../E2E-Execution-Plan.md#task-size-and-order).

## Scope and prerequisites

Deliver **FILE01/02/06 terminal owner, nonsecret submission, help and close**. Named consumer: task **001t** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **001s** — SEARCH01–06 Parent launchable and standard-account unavailable bindings; terminal search entry.

## Read only this context

Read FILE01/02/06, INFO02, terminal methods in [accessible_ui.py](../../../tests/e2e/accessible_ui.py) and [command_help.py](../../../tests/e2e/command_help.py).
Read the affected safety tests and named source callables, not predecessor
briefs or unrelated providers. Current route qualification comes from the
catalogue; a checked historical task does not override it.


## Implementation

Bind the actual terminal owner/window, focused nonsecret input and bounded public output. Reuse FILE01's direct shortcut and implement ordinary close/return, distinguishing command echo from results. Parent app launches belong to PARENT01; case 6 does not consume Terminal.

Keep repository-owned targets addressed by public automation IDs. External
provider bindings use the approved scoped adapter and its ownership, ambiguity,
freshness and uncertain-input guards. Reuse the existing attempt envelope,
observer and worker; add no independent runner or fixture framework.

## Live VM acceptance

Execute the declared installed-help command, independently read its required output and close normally. Qualify independently supplied terminal entry; wrong window, unfocused input, echo-only results and uncertain submission refuse.

Use a fresh guarded VM attempt through shared watchvm intent, display and
command transport. Pass affected cleanup/ownership regressions in isolation
first. Require independent valid entry, wrong-entry refusal, public results,
sanitized collection and owned cleanup. Secret and shared infrastructure changes
retain all applicable regression requirements from the master.

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_terminal_help
```

The selector is planned, not currently qualified. Host checks alone cannot
complete this slice, and it supplies no complete-scenario acceptance credit.

## Close out

Follow the [master close-out](../E2E-Execution-Plan.md#completion-and-document-cleanup).
Record only the actual callable and qualified slice in the catalogue. After
acceptance and cleanup pass, check **001ta**, advance the sole pointer to the
following unchecked row and delete this brief after enduring context is in
source/contracts. Keep any unmet gate and its return condition on this task;
do not advance around it.
