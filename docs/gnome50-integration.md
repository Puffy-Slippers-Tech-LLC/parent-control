# GNOME Shell 50 integration note

The child extension has no lock-screen integration. It does not access
`ParentalControlsShield`, `UnlockDialog`, `AuthPrompt`, `ScreenShield`, the
GNOME Shell Polkit agent, or private `TimeLimitsManager` fields and methods.

GNOME Shell 50 exposes no supported extension API for adding a custom request
control or a custom Polkit action to the stock parental-controls lock screen.
Requests are therefore initiated only from the extension's in-session panel
indicator. A supported lock-screen request flow requires an upstream
GNOME/Malcontent integration point.
