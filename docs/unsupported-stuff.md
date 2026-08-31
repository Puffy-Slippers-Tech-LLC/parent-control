# Unsupported and private integration concerns

## Handoff context

### Primary goal

Show exactly one administrator authentication dialog for a request which does
both of the following:

1. replace the restricted user's remaining session extension by writing
   `SessionLimits.ActiveExtension`; and
2. apply the requested app restrictions by writing `AppFilter.AppFilter`.

Both writes must either consume the one retained combined authorization or run
without user interaction. The second write must never open another
authentication dialog.

### Settled decisions and non-goals

- The custom request flow intentionally writes `ActiveExtension` directly. It
  does not need to call Malcontent's `RequestExtension`.
- A stale packaged extension ZIP is not part of this audit and has been removed.
- The immediate objective is to minimize unsupported integration while keeping
  the one-dialog behavior. Replacing the product's UI or removing lock-screen
  requests is not assumed unless explicitly chosen.

### Verified target environment

The audit was performed against the locally installed Ubuntu 26.04 target
stack:

- GNOME Shell 50.1;
- Malcontent 0.14.0;
- Polkit 127; and
- GJS 1.88.0.

The conclusions about private GNOME Shell fields are intentionally limited to
this target. They must be rechecked before adding another Shell version to
`metadata.json`.

### Key implementation files

- `extension.js` coordinates the combined authorization and the two writes.
- `parentalApproval.js` performs and revokes the combined Polkit authorization.
- `sessionLimitsClient.js` writes `ActiveExtension`.
- `appFilterClient.js` writes `AppFilter`.
- `policy/org.gnome.shell.extensions.oh-no-parent-control.policy` defines the
  combined meta-action and implied permissions.
- `parentalControlsIntegration.js` contains most private lock-screen, Polkit,
  and time-manager integration.
- `requestDialog.js` contains additional private lock-dialog placement.
- `timerQuery.js` uses the supported Malcontent estimated-times D-Bus API.

### Change and validation guard

Do not remove a private workaround merely because its original upstream bug is
marked fixed. First reproduce and measure the current behavior in a booted
GNOME 50/GDM VM with a working system bus. In particular, removing the
time-limits overlay is safe only after all of these checks pass:

1. An approved `ActiveExtension` write causes Malcontent to emit
   `EstimatedTimesChanged` promptly.
2. GNOME Shell consumes the new estimate and leaves `LIMIT_REACHED` without
   calling private manager methods or changing `_estimatedTimes`.
3. A shorter new extension replaces a longer existing extension correctly.
4. Expiry returns the session to the exhausted state and re-locks it as
   expected.
5. The behavior survives Shell/session restart without granting too much or too
   little time.
6. Exactly one authentication dialog appears and both AccountsService writes
   succeed for requests made from both the exhausted shield and the unlocked
   panel entry point.

This project targets GNOME Shell 50 and Malcontent 0.14. Its combined request
flow authenticates one custom Polkit meta-action, then writes
`SessionLimits.ActiveExtension` and `AppFilter.AppFilter` through
AccountsService on the same system-bus connection. Those D-Bus properties,
Polkit's `org.freedesktop.policykit.imply` mechanism, temporary authorization,
and explicit authorization revocation are supported interfaces.

The custom flow deliberately does not use Malcontent's `RequestExtension`.

## Remaining concerns

### Lock-screen Polkit integration

GNOME Shell 50's Polkit agent permits only the native
`org.freedesktop.Malcontent.SessionLimits.Extend` action to open an
authentication dialog while the session is locked. It defers other actions,
including this extension's combined action, until after unlock. GNOME Shell 50
does not expose a supported extension API for adding another action to that
exception.

`parentalControlsIntegration.js` therefore patches the loaded Polkit agent and
depends on private implementation details, including:

- `Main.componentManager._allComponents.polkitAgent`;
- the agent's `_onInitiate` and `_currentDialog` fields;
- replacement of the agent's `initiate` signal handler;
- temporarily changing `Main.sessionMode.isLocked`;
- replacing the authentication dialog's session-mode handler; and
- reparenting the dialog through `Main.screenShield._lockDialogGroup`.

This behavior is specific to the inspected GNOME Shell 50 implementation and
has no compatibility guarantee. Disconnecting every `initiate` handler is
particularly invasive because it can disturb future Shell handlers or another
extension's handler.

There is no completely supported extension-only replacement which preserves a
custom combined authentication prompt on the stock GNOME 50 lock screen. A
helper daemon would not change this: GNOME Shell would still defer the helper's
custom Polkit action while locked. Fully supported alternatives are to request
authorization only after unlock, or to add an upstream/distro GNOME Shell and
Malcontent integration point for the combined operation.

### Time-limits state overlay

`parentalControlsIntegration.js` patches private `TimeLimitsManager` state:

- `_updateState`;
- `_estimatedTimes`; and
- `_updateEstimatedTimes`.

The overlay was primarily justified as a workaround for Malcontent issue #133,
where `EstimatedTimesChanged` was not emitted after granting an extension.
Malcontent 0.14.0 lists that issue as fixed, so this justification is outdated.

The supported path is to write `ActiveExtension`, observe
`EstimatedTimesChanged`, query `GetEstimatedTimes` when needed, and let GNOME
Shell update its own state. The private overlay and persisted local grant should
be treated as removable legacy workarounds after this supported path is
validated in a booted GNOME 50/Malcontent 0.14 environment.

### Other private lock-screen dependencies

Private lock-screen access is not fully isolated to
`parentalControlsIntegration.js`:

- `requestDialog.js` uses `Main.screenShield._lockDialogGroup`.

The lock-dialog-group dependency cannot be removed while retaining a custom
modal above the stock lock screen, because GNOME Shell 50 exposes no public
parent or dialog-placement hook for that purpose.

Adding the request button to GNOME's native `ParentalControlsShield` likewise
depends on private `UnlockDialog`, `AuthPrompt`, shield, Ignore button, and
request-cookie fields. There is no public extension hook for augmenting that
shield. If the lock-screen UI must remain, this access should stay confined to
one small, explicitly GNOME-50-specific compatibility module.

## Recommended direction

1. Remove the private time-limits overlay after verifying the supported
   Malcontent signal/query path end to end.
2. Retain only the unavoidable lock-screen shield and Polkit adapter, clearly
   label it as private GNOME Shell 50 integration, and minimize its effect on
   other signal handlers.
3. Test in a booted GNOME/GDM environment that one authentication dialog is
   shown and that both AccountsService writes succeed.
4. Pursue an upstream GNOME/Malcontent hook as the path to a fully supported
   lock-screen implementation.
