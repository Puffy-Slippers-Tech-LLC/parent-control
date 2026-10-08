# 301 — Qualify the installed product restart notice

Follow the [shared App UI API task contract](../E2E-Execution-Contracts.md#task-brief-contract),
[capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance)
and [scenario acceptance](../E2E-Execution-Contracts.md#scenario-acceptance).
The shared implementation is present; installed qualification remains pending.

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

`check_e2e_restart_notice` is the maintained qualification selector. Its
`RestartNoticeJourney` composes the existing package installation, fresh desktop,
station-entry and independently observed reboot mechanics. Shared
`AccessibleUI.restart_notice` / `restart_action` bind the three exact application
owners; `UiObservations.submit_restart` is the single-use terminal input route.
Observe a genuine installed modal, Close/re-entry without boot change, one normal
authorized kiosk reboot and fresh usability/absent modal on all three targets.
Wrong-owner and missing-modal refusals belong in the installed qualification;
duplicate-ID, ownership, transport and replay refusals are covered by the host
safety matrix. Tasks 302–305 own complete cases separately; no status injection
or manual reboot marker supplies installed acceptance.

After the scoped unit and real GTK modal matrix pass, run these selections on
every selected VM, stopping at the first live failure under the session boundary:

```bash
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_restart_notice
tools/run-tests --vm onpc-Ubuntu26.04 integration check_e2e_customer_reboot
```

The second selection retains the affected shared command-reboot continuity
regression. Both selections start product-free and use source-bound verified
package inputs; automatic preparation belongs to the maintained launcher.
