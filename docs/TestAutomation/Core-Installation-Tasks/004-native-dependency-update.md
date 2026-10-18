# 004 — Qualify native dependency updates during retained sessions

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

## Purpose and scope

Qualify one actual distro-native package maintenance transaction while a
scenario-owned kiosk manager/session is retained. Existing synthetic replacement
and reexec coverage remains required, but cannot prove real package scripts,
vendor PAM changes and native loader behavior. A dependency update made before
fresh product installation establishes a different history.

## Prerequisites and task boundary

Requires: 003, 004a, 004b, 004c, 004d.

[004a](../Core-Installation-Coverage-Handoff.md#task-004a-finite-native-input-review) resolves package-pair feasibility and exact
expected generation behavior; [004b](004b-native-transaction-inputs.md) owns
verified inputs and preparation; [004c](../Core-Installation-Coverage-Handoff.md#task-004c-retained-session-history) owns
registration and host-verified history implementation.
[004d](004d-native-update-histories.md) qualifies one complete history per target
in parallel, with independent ownership and evidence. This final row retains all
original requirements below and reconciles both matching installed receipts and owned
cleanup. It does not require duplicate runs when the retained candidate,
helpers, inputs, baselines and assertions match; rerun an invalidated target's
whole history. Host/review prerequisite passes alone cannot close this row.

## Reading and implementation route

Read the [master](../Core-Installation-Coverage-Handoff.md),
[Kiosk Confinement](../../SystemDesign/Kiosk-Confinement.md),
[Lifecycle](../../SystemDesign/Lifecycle.md),
[installed environment](../../../tests/integration/Environment.md),
[VM mandate](../../Mandates/VM-Mandate.MD),
[test storage](../../Mandates/Test-Storage-Mandate.md) and relevant host
parallelism/cleanup contracts. Inspect the complete `system_kiosk_confinement`
native inventory, replacement, retained-mapping and reexec functions and their
callers before extending them. Reuse their process identities and bounded
watch/transport, never kill a manager merely to make it inactive.

Declare one supported old/new native package pair per distro that exercises an
executable/PAM input the product measures. Supply verified finite transaction
artifacts through maintained preparation/staging, recording versions, package
digests and affected paths. Do not rely on an unbounded internet update or claim
version-change coverage from reinstalling identical bytes. Extend the shared
input builder if needed, with provenance and ownership regressions; do not
repair reusable dependencies during a test. The declared update itself is a
scenario mutation, as permitted by the VM mandate.

Registered selector: `test_native_dependency_update_retained_session` (system ID
**289**); use the [installed runner's bound native-input route](../../../tests/integration/README.md#retained-session-native-dependency-update).
Registration supplies no installed acceptance. No new generic update/fault
framework is needed. If no supported package pair is available,
retain a concrete blocker and required artifact identity.

## Validation and expected results

Run affected host regressions, then the complete registered history on both
targets. Record old inputs and live process identity, perform the native package
transaction, and independently prove the measured bytes changed while retained
process mappings keep their old identity. Verify confinement stays enforcing,
new unqualified execution/admission refuses as specified, a loader cannot publish
over held admission, and safe reexec/retirement follows the product contract.
After normal owned exit and required activation/reboot, verify new native inputs,
fresh-session admission, broker operation and unchanged child policy. Preserve
ordinary-user/vendor behavior and all teardown restrictions.

Collect native versions/digests at both generations and the public recovery
result. Let existing owned cleanup finish on both targets; do not clear foreign
locks or journals. Run `make build` after product/build-input edits, refresh
coverage and links, retain exact target reports and close this final row only
with all required results. Set the master's pointer to none when the queue is
complete; existing customer E2E obligations remain under their own plan.
