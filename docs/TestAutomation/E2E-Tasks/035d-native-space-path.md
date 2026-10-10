# 035d — Qualify a native executable path containing a space

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX06 space-path readiness; FILE05 copy and command-policy result**. Named consumer: task **035a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079d** — APP02 and FLOW08 native launch results without a prior window.

## Implementation

Bind the fixed space-containing baseline executable, exact identical-copy
destination and distinct allowed N. Extend baseline declaration/verification only
for missing reusable assets; verify through FIX06 and perform the recipe's copy
through the shared FILE05 command helper.

## Live VM acceptance

Copy the declared executable on the VM through FILE05; under publicly saved Hard and Soft rules require original/copy denial while N remains usable. Qualify independently prepared owned source/destination fixtures and wrong-path/owner/destination refusal before mutation.

Qualification selector (implement and register before use):

```sh
tools/run-tests integration check_e2e_native_space_path
```
