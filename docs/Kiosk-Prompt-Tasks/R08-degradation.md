# R08 — Keep optional failures out of core entry

Acceptance: host

Required tasks: R07.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md), R07's delivered integration,
the [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[frontend flows](../SystemDesign/Frontends.md#main-flows) and
[admission diagnostics](../SystemDesign/Logging-and-Feedback.md#kiosk-admission-diagnostics).

## Purpose and route

Missing optional data/services must preserve a usable request form and genuine
parent approval. Keep the original cause through bounded recovery and later
diagnostic collection; a healthy later event must not erase the incident.
Read complete affected functions, callers/callees and shared state in the kiosk
startup and `request_content.py`, shared form/resource loaders,
`common/oh_no_parent_control_ui/feedback.py`, broker diagnostic collection and
the [export owner](../SystemDesign/Logging-and-Feedback.md#feedback-and-diagnostic-export).
Read the [portal boundary](../Mandates/Do-Not-Touch-Portal-Mandate.md) before
touching feedback API-related application code; this task authorizes no submission.

## Finite deliverable

Implement the master's family B defaults for artwork, font and historical
catalogue, plus optional audio, notifications and rich-report features. Keep
essential executable/module/plugin/configuration inputs distinct from cosmetics.
Combine one optional failure with actual caller variation and repeated entry;
the core request/approval path remains usable. Permanent core dependency failure
gets an accurate retry/exit surface and never counts as a successful request.
Every hard-entry rejection needs the master's ledger and concrete reachable
risk or actual essential setup/admin policy. Unknown configuration alone is
insufficient; exclude/degrade optional routes before rejecting the whole session.

## Validation and close-out

Select registered affected resource/startup/form, feedback collection, archive
privacy and diagnostic tests through maintained unit/UI launchers. Assert the
original cause, recovery ordering, bounded unavailable states and PII exclusion;
real Parent download after recovery/reboot remains installed R10/R11 acceptance.
Apply the master's mandatory Astra review/revision gate to product fixes, run
`make build` after the final packaged-input edit, and update every supported
translation for new product strings. Finish owned cleanup, record exact inputs
and checks, close only R08 and advance the master pointer.
