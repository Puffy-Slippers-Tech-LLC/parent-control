# C01b — Map feature and approval source

Acceptance: review

Required tasks: C01a.
Estimate: 20–30 min.

Apply the [master task contract](../Kiosk-Session-Confinement-Plan.md#task-execution-contract)
and [cleanup scope](../Kiosk-Session-Confinement-Plan.md#cleanup-includes-committed-code-and-old-plan-active-changes).

## Session boundary and deliverable

C01a supplies session/native interfaces. Map the complete kiosk main/controller/
startup/agent_locale callers and broker authorization/core/service/kiosk_visits
with the D-Bus XML. Compare the release pin, checked-in main and staged,
unstaged and untracked old-plan work; new active modules are not accepted code.

Extend the confinement owner's disposition table with current feature behavior,
approval/cancellation/target-validation responsibilities and obsolete protocol
coupling. Keep current language/preferences, presets, notifications, What's New,
feedback and shared-overlay outcomes. Required grant/policy behavior survives
even when its obsolete confinement mechanism is removed.

Hand exact broker and frontend interfaces to C01/C02b1/C02b and their test
consumers to C01c. Identify removals from committed code and active old-plan
changes separately. Check source references and links/plan structure. No product
changes, new protection design or acceptance of historical implementation.
