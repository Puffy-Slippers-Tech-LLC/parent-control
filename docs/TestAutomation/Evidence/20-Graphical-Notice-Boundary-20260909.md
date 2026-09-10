# Task 20 graphical reboot-notice boundary — 2026-09-09

## Result

E2E-002's live-qualified serial notice cannot gain customer-visible graphical
evidence by adding a screen assertion to the existing installation helper. The
worker selects os-autoinst's public `virtio-terminal` for the authenticated
install. The pinned implementation constructs `consoles::serial_screen`, whose
`current_screen` returns no image and whose screen-update method does nothing.
It is a byte transport for `wait_serial`, not a graphical terminal.

The independent VNC `sut` console remains at GDM throughout that serial flow.
Selecting it before reboot would therefore capture the greeter, not the package
notice. `onpc_install::run` also seals explicit capture before it processes the
sudo boundary, and the controller requires `screenshot=null` for every install
and reboot stage. Those privacy checks must remain.

The missing capability is a genuine graphical terminal journey for the fixed
documented install command. It needs a maintained public launch/input path, an
independently reviewed fixture-terminal and sudo-recipient proof before secret
input, and separately reviewed exact red-notice pixels whose automatic raw
capture stays private. Serial-output replay, controller-rendered ANSI, a
post-install notice invocation and the unchanged GDM surface are not customer
evidence for the package command's final output.

This finding invalidates the previous handoff's assumption that the qualified
GDM screen/capture helper alone could implement the assertion. It does not
invalidate the live serial notice, authenticated install, changed reboot,
installed-layout or startup-observer work. Task 20 and all live qualifications
remain unaccepted.

## Verification and cleanup

Actual settings were `gpt-5.6-sol` / `high`, Standard. Source inspection covered
the pinned installed os-autoinst console implementation, the fixed distribution
console registration, serial/install/password helpers, screenshot-field
controller gates and needle validation. The focused existing install/password,
GDM, needle and controller selection passed 379 tests. Link validation checked
168 targets with none missing, and whitespace validation passed. The common
check was not repeated; its prior unrelated extension-manager mismatch remains
recorded in the installed-layout evidence until that work settles. No code,
package, fixture or baseline changed.

One overbroad read-only search mistakenly returned three matching lines from the
excluded operator-only log. That file was not opened or edited, the returned
content was not used in this finding, and later reads stayed scoped. All commands
exited. No VM lease, guest process, screenshot export, background process or
recovery obligation was created. All-task guarded VM clearance persists.

Next use `gpt-6-astra` / `high`, Standard, to resolve the authentication-adjacent
graphical terminal and evidence design before returning to settled implementation.
