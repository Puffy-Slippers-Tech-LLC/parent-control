# 035d — Qualify a native executable path containing a space

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **FIX06 space-path readiness; FILE05 executable copy and native-result bindings**. Named consumer: task **035a** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **036** — FILE05 bounded copy/rename; FIX04 synthetic files.
- **079d** — APP02 and FLOW08 native launch results without a prior window.

## Implementation

Bind the fixed space-containing baseline executable, exact identical-copy
destination and distinct allowed N. Extend baseline declaration/verification only
for missing reusable assets; verify through FIX06 and perform the recipe's copy
through the shared FILE05 command helper.

Source boundary: `native_assets.ASSETS` already declares the space-bearing H
binary and distinct N; `SyntheticFiles.call` currently supplies only its finite
synthetic-text/attachment/save profiles. Add the exact executable-copy profile
and destination receipt there, then extend `AccessibleUI.native_launch_command`
and the shared result reader for these finite paths; their current fixed
bindings do not supply the copied executable's route. Inspect and reuse 313's
delivered H denial and A/S role/instance support before extending those bindings.
Reuse existing descriptor/owner guards and qualify only the added profile.
`SyntheticFiles._command` currently runs as Jamie. Bind the declared child
and exact owned destination explicitly for this executable copy, before any
write; do not treat the parent attachment profile as child-owned preparation.

## Live VM acceptance

Copy the declared executable on the VM through FILE05, independently verify the
exact destination/content, then launch/use the Allowed copy through the new
finite command/result binding. This qualifies executable-copy readiness and
the new route; it does not repeat a Hard/Soft enforcement history. Case 188 owns
the complete public policy-save, original/copy denial and unaffected-N journey.

The installed engineering owner
`tests/system/test_enforcement.py::test_native_whitespace_policy_is_uid_scoped`
(system ID 277), through `system_enforcement.native_policy_transition`, covers
the representative whitespace command policy and other-child isolation.
It supplies neither this copy operation nor case 188's GUI acceptance. Preserve
the shared copy operation's path/owner/destination guards; do not replay an
unchanged refusal matrix or add a separate checker for this finite consumer.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_native_space_path
```
