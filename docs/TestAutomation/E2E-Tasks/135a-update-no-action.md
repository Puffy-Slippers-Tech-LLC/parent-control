# 135a — Qualify a real update requiring no activation

Use the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Estimate: 20–30 minutes.

## Scope and prerequisites

Deliver **LIFE04 update and LIFE05 no-action notice**. Named consumer: task **135** and any
complete cases released directly by this slice in the canonical queue.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **300d** — Verified old/current package submission, completion and version readback.
- **180** — Public Parent entry, one saved allowance and independent readback.

## Implementation

Bind the verified no-action old/new package pair to the shared LIFE04
administrator SSH package command. Independently read completion and its actual
notice through FILE06 without adding a restart; retain mechanical
activation/migration checks. No Terminal rendering or password-prompt exercise.

Reuse `package_install.submit_release` / `observe_release` and
`package_command.PackageCommand`; the existing `package_upgrade.PLAN` expects a
reboot notice and does not implement this no-action profile.
`PackageCommand.read_result` also requires the final reboot notice for current
upgrade bindings; extend its finite notice contract and affected host checks
before this selector can run. Bind genuine reviewed old/new assets and the
exact no-action result; do not accept a generic successful exit as the notice.
Keep one nondefault allowance comparison on the same usable Parent window; no
request-form tour, policy-edit matrix, retained-child visit or extra reboot is
needed to qualify the no-action operation. Earlier-release activation during
preparation still follows its actual notice through the shared package envelope.

## Live VM acceptance

Install the declared no-action update, independently read the final notice and unchanged usable app entry/settings. Wrong assets, failed completion or an unexpected activation notice refuse.

Planned qualification selector (not registered; implement before use):

```sh
tools/run-tests integration check_e2e_update_no_action
```
