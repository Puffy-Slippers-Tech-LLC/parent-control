# R08 — Preserve causes through fallback and recovery

Acceptance: host

Required tasks: R08a — provisioning-icon fallback; R08b — native agent language;
R08c — optional runtime features.
Estimate: 20–30 minutes.

Read the [master](../Kiosk-Resilience-Plan.md), delivered R07/R08a–R08c inputs,
the [task contract](../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract),
[frontend flows](../SystemDesign/Frontends.md#main-flows) and
[admission diagnostics](../SystemDesign/Logging-and-Feedback.md#kiosk-admission-diagnostics).

## Session boundary

R08a/R08b/R08c extract the independent provisioning, locale and runtime fallback
implementations. This task preserves original-cause/recovery diagnostics, the
accurate permanent-core-unavailable retry/exit surface, and composes optional
failure with actual caller variation and repeated entry. Reuse prerequisite
mechanics/evidence; remaining work is this diagnostic/result composition.

## Purpose and route

Missing optional data/services must preserve a usable request form and genuine
parent approval. Keep the original cause through bounded recovery and later
diagnostic collection; a healthy later event must not erase the incident.
Read complete affected functions, callers/callees and shared state in the kiosk
startup and `request_content.py`, shared form/resource loaders,
`common/oh_no_parent_control_ui/feedback.py`, broker diagnostic collection and
the [export owner](../SystemDesign/Logging-and-Feedback.md#feedback-and-diagnostic-export).
R08a/R08b own the complete provisioning/locale audits and implementation. Inspect
their delivered required-setup/release and ready-agent/request interfaces at this
composition boundary; expand into those complete callers if ambiguity or a new
failure requires it. Preserve their mapped locale/job-ordering expectations.
This task authorizes no submission.

## Cumulative fallback guarantees

Implement the master's family B defaults for artwork, font and historical
catalogue, plus optional audio, notifications and rich-report features. Keep
essential executable/module/plugin/configuration inputs distinct from cosmetics.
Implement native or untranslated authentication fallback for C/C.UTF-8-only
hosts, missing native catalogues and unavailable locale discovery. Separate
cosmetic preparation from the required ready agent and visit identity; preserve
genuine parent authentication and do not accept a stale/failed agent as ready.
An unavailable or invalid optional account icon must allow a display default
without requiring another icon API call, and let required configuration finish,
including safe release of owned quarantine.
Do not release before required enforcement is ready or override administrator
expiry. Cover this pre-GDM failure as well as runtime resource loading.

## Remaining deliverable

Combine one optional failure with actual caller variation and repeated entry;
the core request/approval path remains usable. Permanent core dependency failure
gets an accurate retry/exit surface and never counts as a successful request.
Every hard-entry rejection needs the master's ledger and concrete reachable
risk or actual essential setup/admin policy. Unknown configuration alone is
insufficient; exclude/degrade optional routes before rejecting the whole session.

## Validation and close-out

Reuse applicable R08a–R08c results; run affected composition/startup/form, feedback
collection, archive privacy and diagnostic tests through maintained unit/UI
launchers. Assert the original cause, recovery ordering, bounded unavailable
states and PII exclusion.
Include icon failure with successful required setup/owned release and paired
administrator-expiry preservation.
Cover locale-discovery failure and C-only fallback with correct agent readiness
and request dispatch, preserving job/cancellation ordering. Real approval on the
C/C.UTF-8-only fixture remains family-B acceptance on both installed targets.
Real Parent download after recovery/reboot remains installed R10/R11 acceptance;
R10a/R11a own the complete individual family-B fallback histories.
Apply the master's mandatory Astra review/revision gate to product fixes, run
`make build` after the final packaged-input edit, and update every supported
translation for new product strings. Finish owned cleanup, record exact inputs
and checks, close only R08 and advance the master pointer.
