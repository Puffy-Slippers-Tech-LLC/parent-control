# Parent, child, and shared request UI

[System design overview](../System-Design.md)

Read this for management flow, child/kiosk request behavior, shared GUI
responsibilities, and remembered selectors.

Implementation: [parent main.py](../../parent/oh_no_parent_control_parent/main.py), [parent client.py](../../parent/oh_no_parent_control_parent/client.py), [child extension.js](../../child/extension.js), [kiosk main.py](../../kiosk/oh_no_parent_control_kiosk/main.py), [request_content.py](../../kiosk/oh_no_parent_control_kiosk/request_content.py), [selection_store.py](../../kiosk/oh_no_parent_control_kiosk/selection_store.py).

## Main flows

1. **Manage:** The Parent App selects one child, loads preferences, child-specific
   launchers, and time status, then serializes automatic saves in interaction
   order. App policy applies immediately, including stopping the selected
   child's newly blocked running applications in every retained session.
   Screen-time changes go through
   `SetParentControl`; revocation goes through `RevokeOneTimeGrant` after a
   confirmation that running blocked apps will close.
2. **Child session entry:** On extension startup and after an unlock transition,
   the child component calls `PrepareOwnSession`. The broker re-reads the grant
   under the shared transaction lock. It reconciles and terminates only for an
   expired grant; a current replacement grant returns without changing policy
   or processes.
3. **Child request:** Selecting the panel indicator launches the kiosk GTK form
   as a fullscreen overlay. `GetOwnAccount` fixes and collapses the child
   selector. The overlay loads shared per-child request choices, uses the
   child-only mute value, and calls `RequestOwnAccess`. Cancel or Escape closes
   the overlay; approval briefly confirms success and then closes it.
4. **Kiosk request:** The dedicated GNOME session lists eligible children and
   approvers, loads the selected child's request choices, and calls
   `RequestAccess`. The GNOME session is declared as a kiosk session, which
   disables every XDG autostart desktop file; its complete application set is
   instead the kiosk compositor, request station, and authentication agent
   declared by the session's systemd target. It remains request-only. Cancel or
   Escape returns to the sign-in screen, and approval does so after a brief
   confirmation.

The child overlay and kiosk deliberately use the same GTK request form and
validation. Only account selection, mute surface, broker request method, and
exit behavior differ.

## Request-selector state

Request selector defaults are non-authoritative UI state stored per operating
system user at `$XDG_STATE_HOME/oh-no-parent-control/request-selections.json`
(normally `~/.local/state/oh-no-parent-control/request-selections.json`). Kiosk
remembers the last child and approver; the child overlay remembers only the
approver and always obtains its child from `GetOwnAccount`. Remembered UIDs
are matched against current broker account lists, with the first eligible
account used when a remembered account is unavailable. Local approver selection
takes precedence over the broker's per-child request preference, including when
preferences arrive asynchronously. Preview windows do not persist selections.

## Related design

- For changing D-Bus calls, read [method permissions](Broker.md#broker-interface-and-roles); for approval behavior, read [grant transactions](Broker.md#authorization-and-grant-transactions).
- For countdown/lock behavior, read [expiry enforcement](Screen-Time.md#countdown-and-expiry-enforcement).
- For changing saved request fields, read [State](State.md).
- For feedback, attachments, and diagnostics, read [feedback and diagnostic export](Logging-and-Feedback.md#feedback-and-diagnostic-export).
- For kiosk startup and login ordering, read [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle).
