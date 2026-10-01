# 035d — Qualify a native executable path containing a space

Apply the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and the task-specific scope and acceptance below.

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX04 space-path asset; FILE05 copy and command-policy result**. Named consumer: task **035a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079a** — APP02 and FLOW08 native grid/command policy results.

## Implementation

Bind the fixed space-containing executable and identical-copy destination, plus allowed N. Stage through FIX04 and copy through the shared FILE05 command helper.

## Live VM acceptance

Copy the declared executable on the VM through FILE05; under publicly saved Hard and Soft rules require original/copy denial while N remains usable. Qualify independently prepared owned source/destination fixtures and wrong-path/owner/destination refusal before mutation.

Apply [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Implement and register this fixed argument-free qualification, with its cleanup
coverage, before invoking it:

```sh
tools/run-tests integration check_e2e_native_space_path
```

## Close out

Follow [completion and document cleanup](../E2E-Execution-Contracts.md#completion-and-document-cleanup)
after this task's acceptance and owned cleanup pass.
