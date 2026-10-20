# R05b — Recover owned account quarantine

Acceptance: host

Required tasks: R05a — capability-based required visibility setup.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md#allow-recover-and-reject), R01's
accepted ownership decision, [lifecycle target](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery)
and [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract).

## Session boundary and deliverable

Extract quarantine ownership/release from R05. Read full package-configuration,
provisioning, expiry capture/write, interruption/retry and completion callers.
Implement the accepted transaction/field ownership so interrupted product setup
recovers after required enforcement/configuration succeeds. Restore captured prior
expiry while preserving later administrator denial, including the same-value
write ambiguity resolved by R01. Equality with the saved value alone is not proof.
Never release before required enforcement or overwrite ambiguous/foreign state.
R08a separately makes icon failure optional; provide the required/optional setup
boundary it will consume.

## Acceptance and close-out

Run finite host lifecycle/provisioning tests for interrupted owned setup, successful
retry/release, required-setup failure, explicit prior/later administrator expiry,
same-value ownership and unowned metadata preservation. Keep failure and bounded
recovery diagnostics precise. Apply master product review/revision, resource
review where applicable and `make build` after the final packaged edit. Update
the existing lifecycle/ledger and pass exact inputs to R05/R08a/R09a; complete owned
cleanup. Actual pre-GDM public-entry acceptance remains installed A/B/C coverage.
