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
- `UnlockDialog._otherUserClicked()` transfers control to GDM before cancelling
  the child authentication prompt. Malcontent 0.14 does not install a PAM
  account module, so the greeter cannot independently enforce the exhausted
  child's timer when that existing session is selected again. The extension
  leaves Switch User available, but relocks the child session when its Shell
  observes it return unlocked while `TimeLimitsState.LIMIT_REACHED` remains set.

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
