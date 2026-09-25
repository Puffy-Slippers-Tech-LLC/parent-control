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
   While the window remains open it refreshes the broker's current managed-user
   list every five seconds. Overlapping reads are coalesced, an unchanged list
   does not rebuild the picker, and a newly created account does not disturb the
   selected child's displayed settings. If the selected account disappears, the
   first remaining child is loaded; an empty result shows the existing visible
   explanation. This activates with the next Parent App process and changes no
   saved data.
2. **Child session entry:** On extension startup and after an unlock transition,
   the child component calls `PrepareOwnSession`. The broker re-reads the grant
   under the shared transaction lock. It reconciles and terminates only for an
   expired grant; a current replacement grant returns without changing policy
   or processes.
3. **Child request:** Selecting the panel indicator launches the kiosk GTK form
   as a fullscreen overlay. `GetOwnAccount` fixes and collapses the child
   selector. The overlay loads shared per-child request choices, uses the
   child-only mute preference for future use, and calls `RequestOwnAccess`. Cancel or Escape closes
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
validation. They differ in child selection, remembered selector ownership,
mute field, broker request method, exit behavior, and external Help/About/file
actions. Both forms disable submission until accounts and preferences have
loaded and the selected child's saved screen-time toggle is enabled. The
broker's kiosk method has a broader contract; see
[grant transactions](Broker.md#authorization-and-grant-transactions).

## Public automation identities

The custom daily allowance entry publishes validation rejection in its public
accessible description, alongside the existing visual error. Accepted custom
input restores the ordinary instruction description. This metadata changes with
the next Parent process and changes neither validation bounds nor saved values.

The shared GTK `set_automation_id`/`describe_control` helpers assign a
GtkBuilder object ID as well as the widget's CSS name. GTK 4.22 publishes the
Builder ID through the public AT-SPI `AccessibleId` property. The child
extension's platform-specific `describeControl` helper publishes the same
property through the Shell actor's public ATK object. The CSS or Clutter actor
name alone is not an accessibility identity. Labels and descriptions remain
human-readable and are not selector fallbacks. See the
[GTK implementation](https://gitlab.gnome.org/GNOME/gtk/-/blob/gtk-4-22/gtk/gtkwidget.c),
[AT-SPI provider](https://gitlab.gnome.org/GNOME/gtk/-/blob/gtk-4-22/gtk/a11y/gtkatspicontext.c),
and [ATK accessible-ID contract](https://gnome.pages.gitlab.gnome.org/at-spi2-core/atk/method.Object.set_accessible_id.html).

GTK creates the minimize, maximize and close descendants of `GtkWindowControls`
internally, so application code cannot identify those implementation nodes.
Owned header bars disable implicit title buttons and add one non-extensible
`GtkWindowControls` owner with a stable `*-window-controls` ID. Inventory checks
permit anonymous toolkit buttons only below that identified owner; application
controls elsewhere still require their own IDs, and automation does not select
the internal buttons by translated names, roles, order or geometry.

ID-addressable GTK menu buttons also publish a `menu.popup` action through
their public widget action group. GTK's generic menu-button AT-SPI interface
does not expose its activate signal as a click action and may list inherited
application actions. Consumers explicitly select the unique `menu.popup`
action after ID lookup, then observe the opened menu. They never select an
arbitrary inherited action or target the internal toggle by tree position.
This accessibility addition activates with the next frontend process (`none`)
and requires no saved-data migration.

Identified list rows publish `row.activate` through the same widget-action
mechanism. It emits GTK's documented native
[row activation signal](https://docs.gtk.org/gtk4/signal.ListBoxRow.activate.html)
while the row is sensitive. The preview resolution selector uses this action;
consumers still reveal the row by ID and independently observe the selected
result. Inherited actions or an unsupported AT-SPI focus operation are not
substitutes for row activation. This also activates on the next frontend process
(`none`) and changes no saved data.

Identified native windows/dialogs publish `focus.<automation-id>` actions for
their contained controls. GTK Entry's specialized AT-SPI Action interface does
not expose arbitrary inserted action groups, and GTK's Component provider does
not implement `GrabFocus`/`ScrollTo`. The owning surface action requests normal
GTK focus, including scrolling into view, only for its mapped, visible, sensitive
control in the active native window. Consumers reacquire the ID and verify focus
and reachability before keyboard input; failed or uncertain readback cannot
authorize replay. WebKit controls retain their supported public Component route.

Dialogs publish their originating window/dialog through `CONTROLS`, using the
public [Gtk.AccessibleList](https://docs.gtk.org/gtk4/struct.AccessibleList.html)
boxed value required by the language binding. GTK supplies the inverse AT-SPI
`CONTROLLED_BY`; unmapping removes the relation. Readers require actual
containment or this public owner chain within the identified application.
Preview readers additionally bind each application ID to its live recorded
launch process. Closure requires a complete fresh negative observation and a
positive identified surrounding surface. Read-only waits discard incomplete
trees and repeat the whole observation within the original deadline; a partial
tree never proves presence or absence, persistent incompleteness fails, and
input is not replayed. External terminal return remains
unqualified until its own provider identity contract is available. These GTK
metadata changes activate on the next frontend process (`none`) without a
saved-data migration.

Identified GTK controls publish `DISABLED` from their effective
[`is_sensitive()`](https://docs.gtk.org/gtk4/method.Widget.is_sensitive.html)
state, including inherited disabling. The shared helper updates it on state-flag
changes and local sensitivity notifications: GTK's own accessibility update in
[`set_sensitive()`](https://github.com/GNOME/gtk/blob/gtk-4-22/gtk/gtkwidget.c)
otherwise reports the local property, even under a disabled container. This
keeps the public control state consistent with actual interaction availability;
it does not change widget sensitivity or management policy. It activates on the
next frontend process (`none`) and changes no saved data.

The Parent child selector additionally publishes `child.focus-<uid>` actions.
Consumers first resolve `parent-child-choice-<uid>` using the declared fixture
account UID, then verify its label, request focus through the matching action
and reacquire the focused ID. Enter commits selection separately;
`parent-child-selected-<uid>` supplies independent selected-child readback.
Menu and filter identifiers are explicit semantic keys, independent of their
display labels.

App Limits publishes its row collection as `parent-app-rows`. Each row uses
`parent-app-<launcher hash>` and its access controls retain their explicit state
suffixes. The current match value publishes `parent-app-<launcher hash>-match-pattern`
or `-match-precise` beneath its match button. These public IDs allow complete
bounded policy observations without inspecting saved preferences. They activate
with the next Parent process (`none`) and do not change stored policy.

Request account choices use their account UID within separate child and
approver namespaces, independently of list order. Each selector keeps its ID
fixed and publishes `kiosk-child-selected-<uid>` or
`kiosk-approver-selected-<uid>` on its selected value (`selected-none` while
empty). Readers resolve this identity first and verify the accessible description
as meaning. Duration choices distinguish zero seconds (rest of day) from custom
duration. Their `Gtk.ToggleButton` selection is exposed as AT-SPI `PRESSED`;
switch/checkbox values use `CHECKED`. GTK metadata
changes activate with the next frontend process (`none` package activation).
Child panel metadata activates with the next graphical session
(`session-renewal`). Neither requires a saved-data migration.

The ID provider does not establish compliance for every consumer. Setup/login
and retained legacy tests still require migration where they use unscoped names,
roles, structure or geometry. Repository-owned UI requires public stable IDs.
External GDM, authentication dialogs, GTK file choosers and document viewers
instead follow the provider-specific exception in `AGENTS.md`: prefer available
IDs, then qualify scoped public accessibility semantics and ordinary keyboard
navigation with ownership, ambiguity, input and result guards. Geometry or image
matching is confined to an explicit provider adapter when accessibility actions
and keyboard navigation cannot work reliably. GTK versions that do not publish
Builder IDs cannot qualify the owned GTK ID adapter, but missing IDs alone do
not block an external-provider adapter. Existing passing tests do not waive
those qualification gaps.

The child panel publishes `child-request-button` for the primary request action
and `child-countdown-animation-toggle` for its context-menu setting. The latter
is also reachable with the standard keyboard context-menu action, so automation
can resolve and focus both controls by ID without pointer coordinates.

The feedback editor publishes the GTK-level `feedback-webview` identity. Its
in-memory document also assigns stable DOM IDs and accessible labels to the
actual generated contenteditable editor, formatting controls, style choices and
link editor. WebKitGTK publishes those explicit IDs in the public AT-SPI
`GetAttributes` map (`toolkit=WebKitGTK`, `id=<control ID>`). Its `AccessibleId`
property instead holds a transient accessibility object number; looking for
DOM IDs there incorrectly reports missing descendants even when the tree is
present. See the [WebKitGTK provider implementation](https://github.com/WebKit/WebKit/blob/webkitgtk-2.52.6/Source/WebCore/accessibility/atspi/AccessibilityObjectAtspi.cpp).
The preview and standalone guest readers share `public_automation_id`, which
normalizes this provider contract to the same control IDs used by consumers.
It reads only public AT-SPI metadata; missing IDs and duplicate matches still
refuse input. A provider that truly exposes only the outer WebView remains
blocked. Automation must not substitute DOM structure, labels, roles,
JavaScript evaluation or geometry. The ID-reader correction itself is test-only
and requires no product installation, package activation or saved-data migration.

## Parent controls and shared information

Manually launching `/usr/bin/oh-no-parent-control-parent` as a standard user
shows a branded **Administrator Required** notice with the packaged app logo,
explaining that an administrator must
sign in to manage parental controls. Only the broker's exact `AccessDenied`
reply selects this notice. No management window or authentication challenge is
created; Close exits. Broker outages retain the startup error-report flow.
This Parent-only change activates on the next app process (`none` package
activation); it changes no saved data or child/kiosk behavior.

Screen Limits offers presets 0, 15, 30 and 45 minutes, then half-hour increments
from 60 through 1410, and custom whole minutes 0–1439. The broker/schema also
accept 1440, but that is not an offered Parent UI value. Custom edits debounce
for 350 ms and also commit on Enter or focus leave. Unchanged custom commits do
not start another save. During a custom save the textbox keeps focus and its
caret, allowing more digits; the allowance picker also stays usable so a click
from the textbox opens it immediately. Subsequent custom and preset commits
remain serialized in interaction order. Conflicting controls stay disabled until
the queue drains.
Invalid edits retain the last saved value. Reloading a child's preferences also
restores that value in the custom editor and clears the rejected-draft error,
including when the saved allowance is a preset. Successful autosaves preserve
the active draft, focus and caret. This takes effect on the next Parent process
and requires no saved-data migration. The allowance picker and custom editor are insensitive while
screen-time control is off; the saved value remains displayed. Time status uses
`GetTimeStatus` with no direct cross-account AccountsService read, and retries
temporary failures before showing unavailable.
Revocation is enabled when the last loaded calculated total is positive and
the form is idle, even if the grant balance itself is zero. The broker still
restores strict app policy and terminates blocked apps in that case, leaving
daily time unchanged.

App Limits loads the selected child's catalogue asynchronously on child selection
and creates rows in batches. Unlike the account list, it has no periodic refresh:
reselect another child and back, or reopen Parent, to display installed/removed
launchers. Save-time target resolution at the broker is independent of this UI
snapshot. Search combines with independent match/access filters, each allowing
multiple or no selected categories. Access-rule buttons autosave; the match-rule
dialog has Save, Cancel and Reset to Default.
Isolated rule-generation failures leave the Parent window functional. It queries
the target-authorized `GetPolicyWarnings` method on child selection, after saves,
and with the 30-second status refresh. A persistent `parent-policy-warning`
label identifies affected apps and explains that they or updated versions may
be unrestricted while other controls remain usable. A changed warning set opens
the ordinary error report once; closing it keeps management open. Saved wildcard
choices remain unchanged and recover on a successful broker rescan. Local app
identities never enter the automatic report draft. Transient child-discovery
refresh errors also keep an already-authorized window open and retry; explicit
authorization denial and failure before initial authorization remain closed.
Saved overrides survive a change to allowed at the storage boundary; disappeared
launchers' saved policies survive later visible-row saves. A failed save rebuilds
the controls from the last confirmed preferences using the restoration path
described below. An irreversible termination failure may already have retained
stricter broker preferences; reopening reloads the actual state.
An empty or unrelated precise rule is rejected locally and leaves the editor
open. A wildcard rule reaches broker validation after the dialog closes, so a
rejected pattern uses the normal failed-save/report path. A basename without
slashes is expanded against the app's sole native target directory. Save of
the detected default and Reset to Default both clear the override; Reset saves
immediately without a second confirmation.

There is a current precise-override restoration limitation. A saved explicit
precise choice has `user_saved_match_rule=true` and no patterns, but
`_apply_app_policies` restores `_default_match_rule` for that combination.
For an app with `suggested_patterns`, the displayed choice therefore becomes
the suggested wildcard after child reselection, window reopening or failed-save
restoration; a subsequent `_app_policy_value` can save that wildcard. Custom
wildcard overrides restore from their saved pattern.
The storage contract does not establish correct precise-choice round trips in
this case, and existing E2E declarations do not qualify that branch.

In both request forms, `_update_controls` gates Request on loaded accounts,
preferences, the enabled toggle and no pending request, not custom-value
validity. Invalid custom text displays validation feedback while Request stays
enabled; `selected()` rejects it before preferences are saved or Polkit starts.
Decimals use `.` and accepted fractional minutes are rounded to seconds. On a
successful approval, both forms count down three seconds before their respective
exit actions. Denial and cancellation restore the same editable choices.

Parent and child overlay offer Help and active About website/privacy/support/
license/legal links. Kiosk About is informational with external launches disabled.
The parent has an ordinary Send Feedback action. All three roles share error
reporting, including reporting-only startup failures. Request errors offer an
initially enabled Report this error choice before exit; success and normal
authentication cancellation do not. Kiosk reports hide file choosers and
external privacy links. See [feedback](Logging-and-Feedback.md#feedback-and-diagnostic-export)
for editor, draft, collection, privacy and delivery contracts.

The Parent App's allowance and app-filter popovers use native menu buttons
and scrollable contents that can shrink to the space supplied by the compositor.
Before each opening, the allowance popover measures the space above and below
its button within the current window, chooses the roomier side and caps its
natural height to fit. This keeps its arrow attached to the button on short
displays, including after scrolling or resizing; the presets scroll while
the custom-amount action stays visible.
Its pages scroll on shorter displays, and legend text wraps without imposing a
wide minimum window size. A grid measures the legend's two columns at their
allocated widths so the expanded card follows the wrapped content's height.
The shared About window can resize and scroll so its
legal notices remain reachable on scaled displays. These layout changes load
with the next app process and do not change saved data.

## Child panel preference

The panel's primary action opens one request overlay. Its hover text reports the
remaining time and identifies the primary and right-click actions. The latter
opens **One minute count down animation**, backed by
`com.puffyslippers.oh-no-parent-control.child`'s
`one-minute-countdown-animation` key in the child's GSettings database. The
[schema](../../child/schemas/com.puffyslippers.oh-no-parent-control.child.gschema.xml)
defaults to false. The setting controls final-minute flashing and final-ten-second
icon rotation, applies immediately and survives login/reboot. It neither changes
enforcement nor enables the request form's disabled sound/lightning. There is
no separate child preferences window. Persistence and operability are functional
acceptance; rendering of the effect is outside the specification's scope.

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
scrolling. Automated request-form checks use public IDs to select accounts and
durations, submit at supported scales and verify the submitted values. The screen
dialog checks validate its public scale choices, invalid-dimension feedback and
cancel/recovery behavior. These checks do not compare pixels, geometry or viewer
frames. Manual preview rendering and retained images remain useful review aids;
they establish neither functional acceptance nor installed kiosk/child-session
qualification. The viewer's manual input support is not an automation route.

Both request surfaces use a compact 14-pixel logical base font and GTK's monitor
scaling for HiDPI. Screen dimensions do not add a second zoom to the rendered
interface, and corner controls retain their native logical sizes. At the
reported 1920×1200 output and 125% scale, GTK allocates 1536×960 logical pixels.
The gateway uses 40% of that width. Through 1200 logical pixels of height, the
gateway and form prefer at most 640 and 384 logical pixels of width. Taller
desktops increase both preferred widths in proportion to height, preserving the
1920×1200 gateway proportions while allocating wider form rows with native text
and controls. At 3840×1600 and 100%, these widths are about 853 and 512 pixels.
The gateway still uses at most 40% of desktop width; smaller windows allow a
larger fraction to retain readable controls, and the form fits the opening.
Form content fills the allocated board width so wider frames give their rows
more space instead of adding empty side gutters.

The scene fits three horizontal backdrop bands independently. The central band
uses the original gateway artwork. The side bands use a clean sky/floor plate
and distribute the original crystal, island and moon silhouettes across the
available space. Each silhouette uses one uniform scale for both axes, bounded
by its band's horizontal and vertical scale. Bottom anchors keep stone bases
on the floor, and foreground formations retain their outer screen edge.
Only the original four floating formations move. Lightning sources use the
same silhouette transform and floating offset; targets, lava and snow
exclusions follow the central gateway. No scenery silhouette is stretched to
fill unused screen width.
The form measures against the gateway opening and reserves space above and
below for the curved chains. Both request views render the chains on a shared
coarse pixel grid with nearest-neighbour enlargement. Stepped iron links use
flat cyan and purple highlights, retaining the curved hang and rail attachments
at each display size. Layout diagnostics log allocations, monitor scale,
gateway dimensions, scenery scale and chain gaps without account information.

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

Sound and lightning are temporarily disabled on both request surfaces, and the
mute/unmute button is hidden and insensitive. `REQUEST_MEDIA_ENABLED` retains a
single restoration switch; saved per-child mute values and handlers remain in
place, but cannot unmute the current UI. Muting flushes voices and playback;
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

The Parent App's expandable explanation always shows daily remaining, grant
remaining and their maximum, including when the configured allowance is zero
or today's allowance is exhausted. `_time_status_subtitle` does not branch on
the configured allowance. With screen-time control off, the calculated daily
operand is zero; a displayed zero total is not itself an access restriction.
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
preferences arrive asynchronously. With a production `SelectionStore`, an absent
local approver does not fall back to `last_selected_approver_uid`; the initial
eligible selection remains. Preview windows have no local store and may use
the broker field, but do not persist selectors.

Duration, custom minutes and the soft-app choice still come from the shared
per-child record, so those values follow the child between surfaces. The kiosk's
last selected child and approver instead belong to the kiosk OS user, and each
child overlay has its own OS user's approver selection. Sound settings are
stored separately per child/surface but are not actionable while media is
disabled.

## Related design

- For changing D-Bus calls, read [method permissions](Broker.md#broker-interface-and-roles); for approval behavior, read [grant transactions](Broker.md#authorization-and-grant-transactions).
- For countdown/lock behavior, read [expiry enforcement](Screen-Time.md#countdown-and-expiry-enforcement).
- For changing saved request fields, read [State](State.md).
- For feedback, attachments, and diagnostics, read [feedback and diagnostic export](Logging-and-Feedback.md#feedback-and-diagnostic-export).
- For kiosk startup and login ordering, read [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle).
