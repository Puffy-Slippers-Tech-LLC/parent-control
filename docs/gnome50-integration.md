# GNOME Shell 50 integration note

Verified locally against Ubuntu's `gnome-shell` package `50.1-0ubuntu1.2` by
extracting the JavaScript resources embedded in `/usr/lib/gnome-shell/libshell-18.so`.

## Relevant implementation

- `ParentalControlsShield` is a non-exported `St.BoxLayout` in
  `js/gdm/authPrompt.js`. It creates its native `_ignoreButton` and adds it
  directly to itself. The button calls the timer daemon's `RequestExtension`
  with `("login-session", "", 0, {})` and interactive authorization enabled.
- `AuthPrompt.setAuthBlocked()` lazily creates `_parentalControlsShield` and
  swaps it with `_inputWell` using `replace_child()`. The shield lives until
  its owning `AuthPrompt` is destroyed.
- `UnlockDialog` creates `_authPrompt` in `_ensureAuthPrompt()` and destroys it
  in `_maybeDestroyAuthPrompt()`. `_updateAuthBlocked()` passes true exactly
  when `Main.timeLimitsManager.state === TimeLimitsState.LIMIT_REACHED`.
- `UnlockDialog` listens to `notify::state` on `Main.timeLimitsManager`. The
  manager's `state` is a readable GObject property, and it emits
  `daily-limit-reached` on the transition into `LIMIT_REACHED`.
- `TimeLimitsManager._updateState()` derives that state from its private
  `_estimatedTimes` cache. During an authenticated grant, the extension wraps
  that calculation and floors only `currentSessionEnd` at the approved expiry.
  The wrapper is restored on disable. This prevents a transient regressed
  estimate from driving both the native lock dispatcher and unlock shield while
  leaving manual screen locks intact.
- `UnlockDialog._otherUserClicked()` transfers control to GDM before cancelling
  the child authentication prompt. GDM can independently check the exhausted
  child's timer only when Ubuntu's separate `libpam-malcontent` package is
  installed and its required account rule is present in `common-account`. The
  extension leaves Switch User available and retains its re-lock safeguard for
  systems where that prerequisite is missing or the cached state remains
  exhausted.
- GNOME Shell's built-in polkit agent normally defers any locked-screen
  authentication request except
  `org.freedesktop.Malcontent.SessionLimits.Extend`. The combined time/app
  approval action needs the same exception. Since `polkitAgent.js` is embedded
  in the Shell binary rather than part of this extension,
  `parentalControlsIntegration.js` applies a narrow runtime patch to the loaded
  `polkitAgent` component: it adds the extension's
  `org.gnome.shell.extensions.oh-no-parent-control.ApproveTimeAndApps` action to
  that one allowlist. The patch restores the original method on disable and
  does not change authentication itself.

The manager combines GNOME wellbeing and parental-control timer state, but the
unlock shield is reached only through the parental-controls lock path. The
timer estimate covers both daily schedules and daily quotas; GNOME 50 presents
both through the same native shield and does not expose a separate public
reason enum. Matching the native shield is therefore the safest exact rule.

There is no public extension hook for augmenting `ParentalControlsShield`.
`parentalControlsIntegration.js` contains the only private access, verifies the
shield's style class and that it is currently parented, and appends rather than
replaces the native button. It resynchronizes on time-limit state, session-mode,
and screen-shield activity changes and destroys its actor on every exit path.

Source resources inspected:

- `/org/gnome/shell/gdm/authPrompt.js`
- `/org/gnome/shell/misc/timeLimitsManager.js`
- `/org/gnome/shell/ui/unlockDialog.js`
- `/org/gnome/shell/ui/screenShield.js`
