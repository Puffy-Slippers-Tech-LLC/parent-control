# 301 — Qualify the installed product restart notice

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
This is planned capability work; no implementation or qualification is claimed.

Required tasks (queue IDs; use delivered scope, not predecessor briefs):

- **006** — Verified package installation and public completion/reboot notice.
- **007** — Planned reboot and independent new-boot/greeter observations.
- **048a** — Child request entry, public form observations and ordinary exits.

Estimate: 40–60 minutes.
Session exception: Genuine package installation and three modal bindings require observed session transitions, Close/re-entry and a real authorized reboot within the installed lifecycle qualification.

## Scope and acceptance

Use the queue's [fresh-install regression scope](../E2E-Task-Queue.md#fresh-install-restart-regression-scope)
and [lifecycle behavior](../../Specification.md).

Qualify one reusable public restart-modal operation with Parent, Child App and kiosk bindings. Reuse shared package, app-entry, station/session and reboot mechanics; do not copy them into case workers. Read the modal before language automation. Keep ownership, public-ID ambiguity rejection and single-use input guards. The existing `update-required-*` IDs are owned by [errors.py](../../../common/oh_no_parent_control_ui/errors.py); detection by [reboot.py](../../../common/oh_no_parent_control_ui/reboot.py) and broker [main](../../../broker/oh_no_parent_control/service.py).

Register a maintained qualification selector before executing it; none exists yet. Observe a genuine installed modal, Close/re-entry without boot change, one normal authorized reboot and fresh target usability/absent modal. Wrong-owner/missing/duplicate modal refusal belongs in qualification. Tasks 302–305 own complete cases separately; no status injection or manual reboot marker supplies installed acceptance.
