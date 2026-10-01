# 036g — Place and launch a native desktop entry

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **APP01/02/03 DING desktop entry and usable launch**. Named consumer: task **036b** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.
- **035p** — FIX04 native assets; LIFE04 fixture installation.

## Implementation

Prepare the exact desktop entry from verified fixture assets through shared
per-user filesystem commands and supported permission/trust metadata APIs.
Reuse the bound user's desktop directory and refuse conflicting files. Keep
copying, permissions and trust setup out of DING/Files UI automation. Then bind
the exact DING icon and its actual activation; reuse the owned fixture result
readers. Qualify only this finite preparation and launch route.

## Live VM acceptance

On the VM, prepare and independently verify the declared entry through the
shared command helper, activate it from the desktop and observe one real
usability action. Qualify independent desktop entry and wrong-icon/ambiguous-owner
refusal. A missing supported preparation API is a concrete prerequisite, not a
reason to add a file-manager setup tour.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_desktop_usable
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
