# R01e — Settle readiness and activation recovery

Acceptance: review

Required tasks: R01a — execution owner; R01c — approval/visit lifetime;
R01d — required setup and quarantine boundary.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md),
[lifecycle target](../SystemDesign/Lifecycle.md#prospective-configuration-and-activation-recovery),
[native-language contract](../SystemDesign/Localization.md#translation-lifecycle-and-shared-ui)
and [execution contract](../Execution-Plans.md#execution-and-delegation).

## Session boundary and route

Extract runtime readiness, recovery and update activation from R01. Trace broker
construction through D-Bus registration, `Service._start_policy()`,
`Broker.refresh_enabled_extensions()`, `ExtensionManager.set_enabled()` and
`KioskAgentLocale.prepare()` through complete callers, failures and public effects.
Read manager/admission/activation callers needed to identify one lifecycle owner.

## Deliverable and acceptance

Classify startup prerequisites by the enforcement/operation they protect. Specify
bounded isolation/recovery for child A's unavailable home/extension while healthy
child B completes approval; preserve required enforcement for A and distinguish
permanent global failure. Assign this finite repair to R06b. Native translation
is optional presentation; assign operational-agent fallback to R08b.

Define fresh/preparing/ready/in-use/failed/recovering states, identity ownership,
healthy reuse, one stale-instance renewal, interruption and safe competing-login
wait/attach/conflict outcomes. Preserve live/foreign/replaced state. Choose one
measurable end-to-end deadline through form and authentication readiness; retries
cannot reset it, and human credential-entry time is separate. Map changed inputs
to no action, owned renewal, session renewal or a concretely justified reboot.
Record source/API basis, controls and ledger decisions in existing owners for
R01's integrated review and R03/R04's measured proof. Check links/document
consistency; implement nothing and leave no runtime resources.
