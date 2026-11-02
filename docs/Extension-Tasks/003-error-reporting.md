# 003 — Report extension failures without a crash loop

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system. Requires: 001, 002. Estimate: 30–60 minutes.
Session exception: keep the controlled native failure, visible report and owned
restoration in the same attempt; a fresh snapshot cannot prove recovered behavior.

Read the [master](../Extension-Plan.md), [error-report contract](../SystemDesign/Logging-and-Feedback.md#error-reports),
`ExtensionManager.report_failure`, `ChildExtensionFailed`, `ExtensionMonitor`,
and the existing owned fault/rollback pattern in `system_session_expiry`.

Use a bounded, identity-recorded engineering fault to obtain an actual GNOME
product-extension `ERROR`; restore its exact owned cause afterward. Verify:

- The broker remains available for a child-local load failure and does not
  repeatedly enable the failed extension. Shared unsafe/missing installation
  failures retain their separate startup refusal.
- The existing standard Child App error dialog appears under the correct child's
  graphical session, independently of extension execution. Repeated error signals
  and a broker restart do not create concurrent report windows or overwrite an
  active edited draft. Opening the report sends nothing; do not select Send.
- If failure is observed before the graphical session is usable, reporting is
  deferred and remains possible when the session returns.
- Recovery followed by Shell or whole-bus loss within GNOME's 60-second startup
  crash window, with a replacement Shell still globally disabled, holds further
  activation. It does not prove our extension caused the crash. Ordinary logout
  remains quiet. Restore the cause and use explicit parent recovery; observe
  healthy activation and rearmed monitoring.

Use the [product UI API](../TestAutomation/Application-UI-API.md) for dialog
observations/Close and the existing translations. Do not duplicate report-editor,
delivery, logging or rollback matrices. A crash/fault selector is not yet
implemented; reuse/register the proper system owner, qualify both
targets and complete owned cleanup before closing the task.
