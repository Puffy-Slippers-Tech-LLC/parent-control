# 312c — Check Jordan's reminders and Riley's station deletions

Acceptance: installed
Targets: onpc-Fedora44

Completed on 2026-11-08 after prerequisites **312a, 312b**.

The first installed attempt on Fedora 44 passed Jordan's own overlay reminder
and language readback, and Riley's saved 90-second reminder through station
deletion/Cancel/reopen and deletion/Save/reopened defaults. Both children's
original defaults, request choices, policy and zero grants were preserved.
Collection, worker/callback shutdown, owned cleanup and baseline restoration
passed; the VM was observed off.

The [reminder catalogue](../E2E-Building-Blocks.md#reminder-controls-and-notification-qualification)
owns the qualified scope and shared callables. The focused selector is
`check_e2e_reminder_child_station_binding`, implemented by
[`ReminderChildStationJourney`](../../../tests/e2e/reminder_child_station.py)
and `onpc_kiosk_reminders::child_station`.

Three focused input-safety checks, two existing reminder UI checks,
source/traceability, listing and Markdown links passed; coverage was regenerated.
The complete empty-list
and reboot history remains in [task 312](312-child-reminder-preferences.md).

This short completed record retains that unfinished brief's dependency link;
bookkeeping in this session is limited to Plan B, its queue and this brief.
