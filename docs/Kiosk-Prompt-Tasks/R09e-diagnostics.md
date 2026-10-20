# R09e — Compose diagnostic recovery and download

Acceptance: host

Required tasks: R09d — delivered A–G fixture/history operations.
Estimate: 15–30 minutes.

Read the [master H family](../Kiosk-Resilience-Plan.md#acceptance), R08's
original-cause interfaces, [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[composition preflight](../TestAutomation/E2E-Building-Blocks.md#composition-preflight)
and [diagnostic export owner](../SystemDesign/Logging-and-Feedback.md#feedback-and-diagnostic-export).

## Session boundary and deliverable

Extract H's diagnostic history from R09. Read complete shared incident/recovery,
reboot, Parent download and archive-observation callers. Register one continuous
original-cause incident, recovery, reboot and real Parent diagnostic download
with bounded completeness, privacy and owned restoration. Verify that later
healthy events do not erase the original cause. Reuse existing collection/export
operations; diagnostic collection alone supplies no usable-entry acceptance.

R09 owns H's separate A–F combinations and the final complete matrix. Do not
split this diagnostic history across restored attempts or send feedback. Read
the [portal boundary](../Mandates/Do-Not-Touch-Portal-Mandate.md) before any
feedback API-related application edit.

## Acceptance and close-out

Run finite host composition/registration, archive cause/completeness/privacy and
restoration checks. Record actual selector/input identities and complete history
boundaries for R09 and R10/R11; planned names remain unimplemented. Apply
resource/storage review and master product-repair gates as needed. Complete
cleanup; real reboot/download acceptance remains installed work.
