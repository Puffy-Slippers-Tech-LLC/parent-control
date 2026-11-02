# 005 — Restore the extension from Parent controls

Acceptance: installed
Targets: onpc-Ubuntu26.04, onpc-Fedora44

Category: system. Requires: 001. Estimate: 30–60 minutes.
Session exception: preserve the deliberately disabled child session and its
current policy while observing the actual installed frontend/backend call path.

Read the [master](../Extension-Plan.md), [screen-time model](../SystemDesign/Screen-Time.md#screen-time-model),
`parent/oh_no_parent_control_parent/main.py`'s child-selection load path,
`Broker.recover_child_extension`, `Broker.set_parent_control` and their existing
host tests. Apply the [product UI API](../TestAutomation/Application-UI-API.md).

Qualify the v1.5 recovery entry points with finite deliberate-disable histories:

- Open Parent with an initially selected saved-enabled child.
- Change selection to another saved-enabled child while Parent remains open.
- Turn controls on from saved-off state while GNOME's global switch is disabled.

Observe that each real action reaches its intended recovery path and leaves
our extension configured/active. Use the master's engineering observation rule
to avoid falsely crediting the continuous monitor as the sole frontend repair.
Preserve other-extension choices and other children. Initial/changed selection
does not change time/grants; first enablement retains its specified daily-limit,
stale-grant clearing and rollback semantics. Saved-off selection must not enable
the extension. Reuse existing host authorization/selection-ordering checks.

This is a system fault-recovery check, not a second Parent customer journey or
UI presentation test. The standalone system binding is unimplemented;
register it only after its distinct fault assertions are executable. Verify both
targets and complete the master's cleanup before closing the row.
