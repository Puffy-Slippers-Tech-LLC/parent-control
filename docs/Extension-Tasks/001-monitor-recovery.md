# 001 — Keep parental control active when extensions are disabled

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system/integration. Requires: Baseline. Estimate: 30–60 minutes.
Session exception: keep repeated disablement and its native restoration in one
attempt per target; the capped backoff must be observed without resetting state.

Read the [master's common acceptance and reuse map](../Extension-Plan.md),
[monitor behavior](../SystemDesign/Screen-Time.md#extension-enablement-monitoring),
`broker/oh_no_parent_control/extension_monitor.py`, the existing private-bus
monitor test and `system_graphical_expiry.verify`.

Implement only the missing native GNOME assertions, extending an existing owner:

- As the managed child, disable our extension individually, including a never-loaded
  `INITIALIZED` instance. Without Parent/kiosk/login/restart assistance, observe
  the same broker restore configured/active state and durable membership.
- Disable globally; observe the switch and our extension restored, preserving
  the exact individual enabled/disabled choices for other extensions.
- Use a finite sequence longer than six disablements, including interference
  that makes an activation verification fail. Recovery must continue with delays
  capped at the documented bound, not become permanently read-only/dormant.
  Stop interference, observe healthy recovery and quiet cooldown reset. Observe
  bounded attempts during the burst and no recurring management commands when idle;
  do not build a synthetic performance/stress framework.
- Verify a parent turning controls off wins, eligible children are isolated and
  administrator/kiosk/ineligible targets are not enabled by the monitor. Reuse
  existing host role matrices rather than repeating every class on both VMs.

Record native first-recovery timing separately from test transport overhead;
the normal 0.5–2-second estimate is not a measured guarantee. Prove real root-to-child
session-bus operation and enforcing Fedora SELinux without relaxing policy.
Do not infer manual intent from repeated disablement. Preserve time/grants and
other users throughout. Register the smallest distinct installed selector before
execution; no new selector exists yet. Finish the master's cleanup and record
the actual binding and results for both targets before checking this row.
