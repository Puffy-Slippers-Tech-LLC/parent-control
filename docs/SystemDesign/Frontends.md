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

## Responsive request layout

`make preview-kiosk` and `make preview-child-overlay` use the
[screen preview launcher](../../kiosk/oh_no_parent_control_kiosk/preview.py).
The preview-only **Change Screens** dialog selects physical dimensions and a
GNOME scale label. A disposable Mutter 50 virtual monitor supplies the real
Wayland surface scale and fullscreen allocation; app layout does not simulate
display scale with font sizes or widget transforms. The launcher applies
temporary configurations over its explicit private D-Bus connection, using
Mutter's mode-specific supported scales (including GNOME's rounded fractional
scale labels). It waits for the app to acknowledge the expected allocation and
surface scale and the viewer's receipt of full-resolution video before replacing
an existing session. A failed replacement leaves
the prior session running. Each service and viewer has its own recorded direct
Popen child; cleanup signals only those unreaped children. No host display
settings or product saved data change. Development activation is on the next
preview invocation; no package/service activation or migration is needed.

The operator authorized a development-only exception for Mutter's private
ScreenCast/RemoteDesktop interfaces on 2026-09-09. The
[viewer](../../kiosk/oh_no_parent_control_kiosk/preview_viewer.py) captures the
existing monitor with `RecordMonitor`; it does not create another output.
The launcher checks Mutter 50.x, the viewer requires an explicitly private bus,
and production entry points never import the viewer. PipeWire carries raw RGB
frames to GStreamer's GTK4 paintable sink, with no video encoding or application
layout substitution. A private WirePlumber `policy` profile connects the stream
without discovering audio/camera hardware. Input shares the capture session;
pointer coordinates are expressed in captured physical pixels and converted by
Mutter to the screen's logical coordinates. The virtual seat is initialized
before the app maps. Key/button state is released on viewer focus loss.

The child Shell preview also starts private WirePlumber and relies on Devkit's
single visible monitor. Supplying an additional command-line virtual monitor
would allow the overlay to open on a screen the viewer does not show. Child
preview overlays use the same fullscreen behavior as production.

The rendering contract follows GTK's
[surface scale](https://docs.gtk.org/gdk4/method.Surface.get_scale.html) and
Mutter's [DisplayConfig interface](https://github.com/GNOME/mutter/blob/50.1/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml).
Viewer fitting is a presentation zoom: it does not change the virtual screen.
The 100% pixels mode sizes the captured image in host physical pixels and allows
scrolling. The fidelity regression compares decoded viewer frames from preview
and production `RequestWindow` paths with identical broker data, clock and RNG
inputs supplied only by the test. The comparison permits at most two 8-bit RGB
levels in fewer than 0.5% of pixels, retaining native GPU rendering rather than
forcing a different renderer for screenshot equality. It also checks exact
screen and transformed control geometry and retains per-case pixel metrics.
It also checks real pointer and keyboard delivery, source
dimensions after viewer resizing, and the absence of extra monitors. These
comparisons cover rendering in the same environment, not a complete installed
GNOME kiosk/child session or different user font/theme/color settings.
This reproduces layout and compositor scaling, but does not certify identical
color output, GPU rasterization or physical panel appearance on another machine.

Both request surfaces use a compact 14-pixel logical base font and GTK's monitor
scaling for HiDPI. The form and corner controls have bounded logical sizes;
screen dimensions do not add a second zoom to the rendered interface. At the
reported 1920×1200 output and 125% scale, GTK allocates 1536×960 logical pixels.
The gateway uses 40% of that width. Its desktop width caps at 640 logical pixels;
smaller windows allow a larger fraction to retain readable controls.

The scene fits three horizontal artwork bands independently. The central band
positions the gateway, while the complete left and right bands keep their
crystal islands onscreen. Background pixels and floating masks share the band
transforms; lightning sources use their crystal's band and targets use the
central gateway. Lava and snow exclusions also follow that central geometry.
The form measures against the gateway opening and reserves space above and
below for the curved chains. Layout diagnostics log allocations, monitor scale,
gateway dimensions and chain gaps without account information.

Duration choices reflow between two columns and one, with wrapped captions when
needed. Account captions sit beside selectors on desktop widths and above them
on narrow displays; compact rows show one avatar so names retain space. Request
and Cancel share a row. The normal and custom-duration forms fit the laptop's
1536×960 allocation. Smaller screens, expanded selectors and long messages use
a vertical scrollbar inset from the stationary frame and chain lugs. The
transformed viewport remains within the gateway and leaves space for corner
controls on narrow displays. An external GTK scrollbar shares the viewport's
adjustment and occupies its projected inset rectangle with a 2D allocation, so
its narrow pointer target aligns with the visible track. Results use the same
sizing and overflow container.
Existing request data and package activation classifications are unchanged;
new request windows load the updated UI.

## Lightning audio

Both request surfaces use [thunder.py](../../kiosk/oh_no_parent_control_kiosk/thunder.py)
for generated thunder, with no background music or recorded audio assets. Each
visible flash triggers one short crack followed by a rolling, fading rumble;
its current brightness controls gain and its screen position controls stereo
placement. Return flashes layer over existing tails. Missed flashes are not
replayed after a delayed frame. The stream uses GStreamer's supported
[appsrc interface](https://gstreamer.freedesktop.org/documentation/app/appsrc.html)
with short live PCM buffers to keep attacks near the animation.

The existing per-child mute values still control sound and lightning together.
Audio starts muted while preferences load. Muting flushes voices and playback;
unmuting waits for a fresh visible flash. Successful dismissal fades remaining
effects, and window destruction releases the pipeline. Missing audio output
disables sound without preventing requests. Logs report state and error codes,
excluding device names and backend debug strings.

This retains the kiosk payload's `session-renewal` package activation class;
new request windows load the updated code. The runtime package uses GStreamer Base and Good plug-ins
for PCM playback and audio output; the former MP3 decoder dependency is removed.
Saved preferences are unchanged and require no migration.

## Remaining-time explanations

Parent remaining-time labels and the child/kiosk estimate use the shared
`common.oh_no_parent_control_ui.duration.format_duration` formatter: `1h 17m`,
`2h` for exact hours, and seconds when needed to preserve partial minutes.

The Parent App's expandable explanation describes current remaining time. A
configured daily allowance of zero shows only the one-time grant remaining.
With a positive configured allowance, it shows both remaining amounts and says
that the larger applies, including when today's allowance has been exhausted.
It does not show an additional request operand or internal property names.

The shared child/kiosk form uses its existing footer for the estimated time
remaining if approved. Fixed-duration choices query `GetTimeStatus` with the
selected child and requested additional seconds. Selection changes are debounced,
reads are serialized, and replies for superseded selections are discarded. The
form refreshes every 30 seconds while idle; rest-of-day requests instead say
that access lasts until midnight. Approval still recalculates the actual grant.
Loading, validation, denial and approval-in-progress messages take precedence.
An unavailable estimate does not prevent submitting a request. Closing the window
removes refresh timers and makes outstanding estimate replies inert.

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
