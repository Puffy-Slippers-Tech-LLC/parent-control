# Supported integration boundary

The child extension does not integrate with GNOME Shell's lock screen. In
particular, it does not inspect or modify `ScreenShield`, `UnlockDialog`,
`AuthPrompt`, the Polkit agent, or `TimeLimitsManager` private state.

The child request UI is available only through its in-session panel indicator.
When a request is approved, it uses supported AccountsService properties and a
single custom Polkit meta-action:

1. `SessionLimits.ActiveExtension` is written for the requested time; and
2. `AppFilter.AppFilter` is written with the requested restrictions.

Both writes use the same system-bus connection and the Polkit
`org.freedesktop.policykit.imply` annotation, so the second write is
non-interactive. The extension then relies on Malcontent's supported
`EstimatedTimesChanged` signal and `GetEstimatedTimes` API; it does not overlay
or alter GNOME Shell's time-limit state.

GNOME Shell 50 has no supported extension API for adding a custom request
button or custom authorization dialog to the stock lock screen. A future
lock-screen flow requires an upstream GNOME/Malcontent integration point.
