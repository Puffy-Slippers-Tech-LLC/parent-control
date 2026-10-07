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
   confirmation that running blocked apps will close. Opening confirmation
   queries the selected child's running soft-blocked policy IDs. The dialog
   shows matching catalogue entries as bullets with icons beneath “These
   running soft blocked apps will be closed:”; the section is omitted when
   none are running. Names and icons reuse App Limits' loaded catalogue and
   icon renderer, including replacement-launcher policy matching. The confirmed
   action stays bound to the child whose apps were reviewed.
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
   disables every XDG autostart desktop file. Its systemd target starts the kiosk
   compositor, request station, notification provider, and authentication agent.
   The target also conflicts with Ubuntu's `update-notifier-crash.path` and
   `update-notifier-crash.service`: those systemd units bypass XDG autostart and
   could otherwise open Apport above the station. This exclusion applies only
   to the kiosk user's session; ordinary desktops retain crash reporting.
   It remains request-only. Cancel or
   Escape returns to the sign-in screen, and approval does so after a brief
   confirmation.

The child overlay and kiosk deliberately use the same GTK request form and
validation. They differ in child selection, remembered selector ownership,
mute field, broker request method, exit behavior, and external Help/About/file
actions. Both forms disable submission until accounts and preferences have
loaded and the selected child's saved screen-time toggle is enabled. The
broker's kiosk method has a broader contract; see
[grant transactions](Broker.md#authorization-and-grant-transactions).

The overlay's `com.puffyslippers.OhNoParentControl.ChildRequest` application ID
has a matching, publicly readable desktop entry using the product launcher icon.
The entry is hidden from the app grid and launches `oh-no-parent-control-child`;
GNOME uses it to identify overlay windows in the dock. It activates on package
installation/update and the next overlay launch, without a service restart or
saved-data migration.

## Application UI API

Parent, kiosk/child request windows, their shared dialogs and the child panel
expose the versioned session-bus `ApplicationUI1` protocol. The
[API reference and control inventory](../TestAutomation/Application-UI-API.md) owns methods,
canonical values, endpoints and dynamic identity families. Python consumers can
use `UIClient.getElementById`, value/text properties or `ui.setText(id, text)`.
Other languages use the same JSON-valued D-Bus methods.

Transport and clients are desktop-neutral. A GTK adapter resolves native
Buildable identities and effective control state; the child panel uses a thin
GNOME adapter for its session and panel availability. A future desktop adapter
can implement the same public contract without changing consumer IDs/operations.
The shared GTK request form continues to serve both overlay and kiosk.

Inputs use existing UI widgets/signals and shared user handlers, including
normal validation, automatic saving, dialog responses and editor draft updates.
Selectors expose canonical language-independent values independently of their
translated captions and popup lifetime. No AT-SPI tree, geometry, display scale,
keyboard focus or desktop-specific pointer stream is involved. Application page
visibility, effective sensitivity, modal ownership, target uniqueness and broker
authorization still apply. External authentication and file choosers retain
their separate provider boundaries.

Registration follows application/extension lifetime. Same-user credentials,
bounded arguments and operations, owner-pinned clients and single-use mutations
prevent stale processes or uncertain calls from becoming silent input retries.
Input completion does not establish a completed backend save. The existing
accessibility routes below remain available; UI and E2E share the public API
facade described in the test inventory. GTK changes load in a new
frontend process; the child payload follows `session-renewal`. No migration is
needed.

## Public automation identities

The following accessibility metadata remains available to assistive technology
and identified harness fixtures. Product UI and E2E tests use the
[Application UI API](#application-ui-api) for both observations and input;
these compatibility interfaces are not alternate product automation routes.

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
application actions. Accessibility clients can select the unique `menu.popup`
action after ID lookup. Product tests instead set a canonical menu command
through the UI API; when opening a menu is necessary, its ordinary API
`activate` operation owns it.
This accessibility addition activates with the next frontend process (`none`)
and requires no saved-data migration.

Identified list rows publish `row.activate` through the same widget-action
mechanism. It emits GTK's documented native
[row activation signal](https://docs.gtk.org/gtk4/signal.ListBoxRow.activate.html)
while the row is sensitive. The preview resolution selector uses this action;
its harness consumers resolve the row by ID and independently observe the result.
Product selector tests use canonical API values. This also activates on the next frontend process
(`none`) and changes no saved data.

Identified native windows/dialogs publish `focus.<automation-id>` actions for
their contained controls. GTK Entry's specialized AT-SPI Action interface does
not expose arbitrary inserted action groups, and GTK's Component provider does
not implement `GrabFocus`/`ScrollTo`. The owning surface action requests normal
GTK focus, including scrolling into view, only for its mapped, visible, sensitive
control in the active native window. These actions remain accessibility
compatibility features. Product tests use API text/value setters and ordinary
activation; keyboard focus and the WebKit Component interface do not gate them.

Parent also publishes the read-only session-bus interface
`com.puffyslippers.OhNoParentControl.Accessibility1` at its existing application
object path `/com/puffyslippers/OhNoParentControl/Parent`.
`GetNativeSurfaceTransform("parent-window")` returns the fresh pair of doubles
from GTK's public `Gtk.Native.get_surface_transform()` for exactly one mapped,
visible, active Parent window. Missing, ambiguous or unavailable surfaces refuse.
Before returning coordinates, the provider uses `Gdk.Display.sync()` and
revalidates the same window. This finishes queued window-system requests,
including prior popup teardown, before a separate native-input connection binds
the compositor's focused window. GTK's active toplevel alone does not prove that
a dismissed popup has released compositor focus.
The interface registers and unregisters with the application; it exposes no
policy data or input operation and needs no new service or saved-data migration.

GTK's AT-SPI WINDOW bounds omit this native offset, including window shadows.
The interface remains compatibility metadata and supplies no permitted route for
product tests. Parent allowance selection uses the scoped API canonical value
and independent saved-value readback, with no geometry or native stream binding.

Dialogs publish their originating window/dialog through `CONTROLS`, using the
public [Gtk.AccessibleList](https://docs.gtk.org/gtk4/struct.AccessibleList.html)
boxed value required by the language binding. GTK supplies the inverse AT-SPI
`CONTROLLED_BY`; unmapping removes the relation. The UI API reports the owning
surface through `parent_id`; product readers use the pinned application/PID and
that explicit surface scope. Preview readers also bind the application to its
recorded launch process. Closure requires a complete fresh negative observation
and a positive identified surrounding surface. Read-only waits discard
incomplete inventories and reacquire within the original deadline; incomplete
reads never prove absence and input is not replayed. These GTK
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

The Parent child selector additionally publishes `child.focus-<uid>` actions for
accessibility compatibility. Product tests set `parent-child-selector` to the
declared account UID through the UI API;
`parent-child-selected-<uid>` supplies independent selected-child readback.
Menu and filter identifiers are explicit semantic keys, independent of their
display labels.

App Limits publishes its row collection as `parent-app-rows`. Each row uses
`parent-app-<launcher hash>` and its access controls retain their explicit state
suffixes. The current match value publishes `parent-app-<launcher hash>-match-pattern`
or `-match-precise` beneath its match button. These public IDs allow complete
bounded policy observations without inspecting saved preferences. They activate
with the next Parent process (`none`) and do not change stored policy.
The match button's public description includes `Current match rule: <rule>`.
The editor content publishes `parent-match-rule-app-<launcher hash>` so an
independently opened dialog can be bound to its app before input. Its entry
retains the shared `parent-match-rule-entry` ID and public native focus action.

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

The ID provider does not establish compliance for every consumer. Product tests
resolve stable IDs through the UI API, independent of AT-SPI ID exposure.
External GDM, authentication dialogs, GTK file choosers and document viewers
instead follow the provider-specific exception in `AGENTS.md`: prefer available
IDs, then qualify scoped public accessibility semantics and ordinary keyboard
navigation with ownership, ambiguity, input and result guards. Geometry or image
matching is confined to an explicit provider adapter when accessibility actions
and keyboard navigation cannot work reliably. Missing IDs alone do not block an
external-provider adapter. Existing passing tests do not waive its qualification
requirements.

The child panel publishes `child-request-button` for the primary request action
and `child-countdown-animation-toggle` for its context-menu setting. The latter
is also reachable with the standard keyboard context-menu action. Product tests
use the `child-panel` API to activate the request action, set/read the animation
boolean and read countdown/tooltip text without native gestures or focus.

The feedback editor publishes the GTK-level `feedback-webview` identity. Its
in-memory document also assigns stable DOM IDs and accessible labels to the
actual generated contenteditable editor, formatting controls, style choices and
link editor. WebKitGTK publishes those explicit IDs in the public AT-SPI
`GetAttributes` map (`toolkit=WebKitGTK`, `id=<control ID>`). Its `AccessibleId`
property instead holds a transient accessibility object number; looking for
DOM IDs there incorrectly reports missing descendants even when the tree is
present. See the [WebKitGTK provider implementation](https://github.com/WebKit/WebKit/blob/webkitgtk-2.52.6/Source/WebCore/accessibility/atspi/AccessibilityObjectAtspi.cpp).
The shared `public_automation_id` reader retains this provider normalization for
accessibility compatibility. Product preview and installed consumers use the
finite packaged editor adapter in the [Application UI API](#application-ui-api).
They set plain text, retained selection, formatting and history through fixed
operations and independently read the public document delta. An outer-only
WebView accessibility tree is no longer a product-test blocker. Missing API
capabilities still refuse; arbitrary DOM selectors, caller-supplied JavaScript,
HTML injection and geometry are not alternate routes.

## Personal language selection

Parent and child overlay read `GetOwnLanguage` asynchronously at startup.
Kiosk reads `GetChildLanguageContext` for the selected child at startup and on each
child selection, applying that child's saved language or using its AccountsService
desktop language and opening setup when unset.
An empty value opens a modal language chooser. Parent retains its
[own dialog UI](../../parent/oh_no_parent_control_parent/language_dialog.py);
kiosk and child overlay use a separate
[metal-board dialog](../../kiosk/oh_no_parent_control_kiosk/preference_dialog.py).
Both choosers belong to the owning GTK application, remain transient and modal,
and restore chooser focus if an outside click activates their parent. Outside
clicks and window-manager close requests do not dismiss them; Save and Cancel
own dismissal.
Its default is the primary session message language from `GLib.get_language_names`,
except kiosk uses the selected child's desktop language when available,
resolved against the shared
[catalogue](../../common/oh_no_parent_control_ui/languages.json); unsupported locales
use English. The [locale resolution policy](Localization.md#language-catalogue-and-resolution)
owns regional/script choices and aliases, including separate Portuguese and
Chinese variants. Both lists scroll through the catalogue's hardcoded priority
order while keeping Save and Cancel outside the list.

Parent fades its window shade in when the language chooser maps and out when it
unmaps, respecting GTK's animation setting. After a successful save, the chooser
is destroyed before relabeling the existing management controls; reopening
Preferences does not relabel an unchanged active language. For first-time
setup, the chooser paints before the management interface is constructed in a
later main-loop iteration behind it; account loading then runs asynchronously.
A saved language is applied before constructing the management interface.
If account loading fails fatally, Parent dismisses the language chooser immediately
and shows the error report instead. Management stays disabled, and closing that
report exits the app. Dismissal does not save or apply the chooser's candidate;
outstanding language replies cannot reopen setup or update its destroyed controls.

The chooser lists native names in catalogue order. Search matches native names,
English names and language IDs, with case-insensitive partial and wildcard matching.
Both dialog UIs use the
heading “Choose your language”. Save
and Cancel are available on all surfaces, including first-time setup.
Selection immediately translates the existing chooser controls in a private
context without remapping the window. Cancel continues without saving or applying
the candidate to the owning frontend; an unset language
prompts again next launch, or when that child is next selected in kiosk.
Save persists the
current user's selection through `SetOwnLanguage`, or the selected child's
selection through kiosk-only `SetChildLanguage`, before closing; failures keep
the selection visible and permit retry. A nonempty saved value suppresses the
startup dialog. The top-right menu's Preferences action opens the same chooser
with the saved selection. Successful saves apply the new presentation context
under the [translation lifecycle](Localization.md#translation-lifecycle-and-shared-ui),
preserving in-progress work and operating-system locale settings.
The overlay uses the child's personal setting; the kiosk
uses the selected child's setting, independently of the approver.
Child changes discard superseded language replies. Relabeling updates existing
widgets in one main-loop turn; unchanged languages skip relabeling, and child
changes retain the visible form without sensitivity flashes or reconstruction.
All dialogs reuse `selected_language` in the shared catalogue module for saved
selection and session fallback. Request controls wait for startup language setup.

Both dialog UIs publish `language-dialog`, `language-search`, `language-list`,
`language-choice-<lowercase-id>`
and `language-continue` (the Save action), plus `language-cancel` on all surfaces,
scoped to their owning
application and window, with the
shared public owner relation and control metadata. The main content publishes
`parent-language-loading` or `kiosk-language-loading` until the initial
choice is saved, setup is cancelled or an existing selection is read,
then the matching `*-language-ready`.
The common host/E2E `complete_language_setup` helper waits for this
startup result, clicks Save once if needed, and independently observes
closure and readiness. It leaves a subsequently opened Preferences dialog alone.
Host preview launch and installed entry checkpoints use its
`complete_parent_language_setup` and `complete_request_language_setup` wrappers.

## Parent release notes

Parent asynchronously queries `GetOwnWhatsNew` after constructing management.
The broker owns current-version selection, audience, fresh-install/upgrade
eligibility and persistence under the [backend contract](State.md#whats-new-backend).
No matching Parent record hides the “What's New” menu item; a matching record
adds it immediately before About, including after acknowledgement.

Automatic presentation waits for language setup and successful account discovery.
Save applies the selected language before opening notes; Cancel destroys the
chooser before notes use the session default. Other visible Parent modals defer
automatic presentation. Fatal discovery and window closure discard late replies.
Each window attempts automatic presentation at most once; query or presentation
alone never persists acknowledgement. Closing a successfully mapped note, through
Close, the top close control, Escape or window close, calls
`AcknowledgeOwnWhatsNew`. A failed write leaves broker eligibility unchanged and
reports a nonfatal notice; a later manual close or launch can retry.

The Parent-only [dialog](../../parent/oh_no_parent_control_parent/whats_new_dialog.py)
uses the logo, a version heading, a scrollable notes card and persistent footer
actions. It inherits the Parent translation context. The versioned release-note
catalogue translates Markdown before the
[native renderer](../../parent/oh_no_parent_control_parent/release_markdown.py)
builds headings, paragraphs, ordered/unordered lists, quotes, separators, fenced
code and inline bold/italic/strike/code/HTTP(S) links. Raw HTML and image syntax
stay literal and load no external resources. The optional See More action is
shown only for a supplied HTTP(S) link and uses the system URI handler.
Kiosk and child overlay UI remain outside this implementation.

## Child reminder preferences

The shared request-screen preferences window has Language and Reminders tabs.
Language keeps its existing search, native-name choices, public IDs and private
candidate translation context. Both tabs use the same list frame and scrollbar
CSS; the armored Cancel/Save actions stay outside the lists.

Reminders loads the selected child's authoritative backend configuration on
first opening that tab. Defaults come from the backend, and saved empty lists
remain empty. Rows sort by ascending trigger seconds. The larger caption is
literal custom text or the translated default; the smaller gray caption is
always the translated trigger duration. There is no synthetic custom preset.

Add/Edit opens a separate modal metal-board editor with reminder text, a
character counter and minute/second timing controls. New text is limited to 50
characters; existing longer backend text can be retained unchanged when editing
its trigger. Equal trigger seconds, including minute/second equivalents, show a
footer warning and disable editor Save. The edited reminder excludes its own ID
from that comparison. Editor Save updates only the preferences draft; Cancel
discards that edit. Preview beside the text field sends the current literal text
or translated default duration through the child extension's reminder-preview
service, using the same `reminderBanner.js` renderer as real countdown reminders.
Desktop previews pass the editor's language through `PreviewLocalized` and use
a private translation context for controls and countdown captions, independent
of the panel's cached language. Legacy preview methods remain supported.
Pressing Preview changes its icon to an up arrow and its translated label to
“See screen top” for three seconds, then restores Preview. Another press restarts
the three seconds; closing the editor cancels the label timer.
The dedicated kiosk uses its own freedesktop notification provider. Both use
the product logo and Critical urgency even when the fullscreen
preference is disabled. It does not save the draft. Invalid timing disables
Preview; delivery failures retain the edit and show an error. Dismissal closes
the preview, including a delivery reply arriving after editor disposal. Preview
does not change reminder thresholds or saved settings. Main Cancel discards the draft;
main Save persists changed reminders and then the language selection. If the
subsequent language write fails, the reminder write has already committed; the
dialog retains the language candidate for retry. Below the reminder list, a
single “Show reminders in full screen apps (games, videos, etc.)” switch edits
the selected child's account-wide `show_in_fullscreen` field in the same draft.
It has a standard-font caption without a subtitle, and is disabled until the
configuration loads, when the reminder list is empty, and while saving. Its
saved value is preserved while disabled. Notification urgency belongs to the
notification backend, not the dialog.

The dedicated session starts `oh-no-parent-control-notifications.service`, a
bounded freedesktop notification provider with one active banner. It uses GNOME
Kiosk 50's documented `gnome-kiosk-notification` client tag to keep the banner
above fullscreen windows without making it fullscreen. A transparent monitor-wide
top strip centers its bounded banner card within the tagged surface; the default
tag's top-left positioning does not position the card itself. This provider does not
start in ordinary child desktops, where GNOME Shell owns notifications. The
provider reads only packaged logo/HUD artwork, supports literal escaped body text,
replacement and dismissal, and does not log reminder content. Its user unit
and kiosk target changes activate with session renewal.

The child extension owns `com.puffyslippers.OhNoParentControl.ReminderPreview`
at `/com/puffyslippers/OhNoParentControl/ReminderPreview`. `Preview(s text, u replaces)`
returns a persistent preview ID for legacy callers. `PreviewTimed(s text,
u replaces, u seconds)` includes the editor's selected duration; `Close(u id)`
only dismisses that sender's current preview.
The service validates session-bus Unix credentials, bounds text and concurrent
credential lookups, refuses locked/greeter sessions, and closes on sender loss
or extension disposal. It accepts literal rendered editor text, not saved policy.
Desktop delivery never falls back to a generic Shell application notification.
Countdown and preview share one banner slot: a new threshold replaces a preview
immediately, and closing an old preview cannot close a newer countdown banner.

Child and kiosk reminders share packaged pixel SVG rails/action icons, the
request form's Monocraft font, dark HUD face, cyan heading and five-segment
countdown. The armored rails have cyan/violet beveled plates and orange corner
accents, six-sided corner plates with straight outer chamfers and thin rails;
the 15-pixel bold cyan heading sits above the
12-pixel caption and progress bar. The countdown also uses 12 pixels so fallback
glyphs, including dense Chinese and Japanese scripts, remain readable.
The product logo is 56 pixels and action icons
are 40 pixels; the Shell card starts at 517 logical pixels and grows with the
translated action widths, bounded by the monitor width. Both renderers retain
compact inner spacing and centered action icons.
Height follows the content. Literal reminder
text wraps naturally.
Action caption widgets are removed; their translations remain for tooltips
and accessibility. The icon buttons
share a centered horizontal action row and retain translated accessible names.
Hovering either icon shows its translated caption in a tooltip; Shell tooltip
chrome is owned and destroyed with the banner, and kiosk uses native GTK tooltips.
Each countdown segment represents one second and empties as a whole block;
the bar never drains continuously within a segment.
Shell registers Monocraft with the actor's Clutter font map, so it is available
to the actual text renderer rather than only Cairo's separate default map.
The child renderer owns only its own Shell chrome and notification model,
without registering it with the message tray: the tray's fixed noncritical
timeout cannot express persistence independently of fullscreen urgency.
High urgency waits outside fullscreen; Critical appears above fullscreen.
An unlocked visible delivery at 60 seconds or more starts a five-second
monotonic deadline and countdown; shorter deliveries persist without a bar.
New banners dispose the old source, actor, signals and timer. Locking, extension
disposal and editor dismissal also retire the owned banner. Old preview IDs
cannot dismiss a newer banner. Preferences dismisses the banner and activates
the existing request application's `preferences` action, or launches the child
overlay with `--preferences` when needed. Both banner entry paths select the
Reminders tab, including in an already-open Preferences dialog. The request
screen's menu and startup language setup open Language. Dismiss retires only
that banner.
The kiosk provider receives the duration/language in bounded notification
hints and uses the same timing rule and shared application action.
These payload changes activate with session renewal and need no migration.

Read failures show a retry action without substituting defaults. Save failures
retain the draft and allow retry. Dialog disposal and selected-child revisions
discard stale asynchronous replies. The overlay uses caller-scoped notification
methods; kiosk uses selected-child methods with the same kiosk/eligible-child
authorization boundary as its language methods.

Public controls are `preferences-tabs` (canonical `language`/`reminders`),
`preferences-tab-language`, `preferences-tab-reminders`,
`preferences-close`, `reminder-list`, `reminder-status`, `reminder-add`, `reminder-retry`,
`reminder-show-in-fullscreen` (boolean), and
`reminder-<stored-id>-text|trigger|edit|delete`. The separate editor publishes
`reminder-editor-dialog`, `reminder-text`, `reminder-text-count`, `reminder-value`,
`reminder-value-increase|decrease`, `reminder-unit` (canonical `minute`/`second`),
`reminder-duplicate-warning`, `reminder-editor-error`, and
`reminder-editor-preview`, `reminder-editor-save|cancel|close`. Stored IDs remain stable through edits;
new rows receive unique IDs. Host checks establish local behavior only; installed
acceptance remains planned in the task queue.

## Localization infrastructure

See [Localization](Localization.md) for the shared GNU gettext infrastructure,
language resolution, settings backend, GTK and Shell translation contexts,
message authoring, packaging and validation. Shared dialogs inherit their owning
frontend's context; language changes preserve the frontend's model and active
work. This module owns the chooser surfaces and their public UI identities.

## Parent controls and shared information

Parent presents a loading window before checking broker permission on a worker;
reactivation reuses it and closing it prevents a late reply from reopening UI.
Only the broker's exact `Error.RebootRequired` status opens the shared restart
modal in Parent, kiosk and child overlay. It is not inferred from generic
service errors or the operating system's global reboot marker. Parent startup
shows only the restart dialog instead of constructing another notice or management
window; Close exits the app. Request forms retain a restart result and their
ordinary exit action.
Repeated callbacks reuse one modal and cannot overwrite the known reboot reason
with a generic language-loading failure.
Kiosk-only read endpoints remain available before reboot so its remembered
eligible child and language can be resolved. A pending restart notice waits
for that initial language read, skips the language chooser and inherits the
request window's translation context. Policy and language writes
remain unavailable until reboot.
The broker uses the shared GTK-independent
[product reboot detector](../../common/oh_no_parent_control_ui/reboot.py) for
both fresh installation and upgrade requests; apps do not duplicate marker
interpretation. The notice asks for a restart without assuming an upgrade.

The modal defaults to Close, which does not reboot. **Reboot now** uses GTK's
standard `destructive-action` style and asynchronously calls logind's public
`Reboot(true)` as the frontend user. Normal system authorization and inhibitor
policy remain in force; no product privilege grant or forced-reboot fallback is
added. Pending requests disable repeated activation; refusal shows a localized
error and restores the choices. Tests substitute only this transport, never
rebooting the development host. The notice and button share all 62 catalogues.

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
Keyboard controllers on the allowance selector and its popup collect explicit
`m`/`h` preset input silently and display a matching offered option as a pending
choice, including its popup selection marker and accessible description, while
the popup stays open. The committed index changes only on confirmation.
Each exact preset match clears the accumulated text while retaining its pending
index, allowing another complete choice to be typed immediately before confirmation.
An explicit GTK viewport scrolls each buffered preset into view using
`Gtk.Viewport.scroll_to`, without moving keyboard focus. Custom remains in the
fixed footer outside the scrolling list.
Incomplete or invalid typed text leaves the committed option displayed;
raw input never replaces the label. Up/Down buffer adjacent options, and `c`
buffers Custom. Enter confirms a buffered choice through the existing selection
handler and closes the popup; confirming Custom focuses the inline entry.
Escape closes the popup without changing the allowance. Focus leave, popup
closure and preference reload also discard unconfirmed input. The custom entry is outside these
controllers. Typed values must exactly match a preset; no rounding is applied.
The allowance MenuButton subclass makes the identified selector its single
closed-popup tab stop and public focus recipient, while the opened popup uses
GTK's native traversal. This avoids delegating focus to an anonymous internal
toggle and leaves keyboard recipient checks addressable by the selector ID.
Invalid edits retain the last saved value. Reloading a child's preferences also
restores that value in the custom editor and clears the rejected-draft error,
including when the saved allowance is a preset. Successful autosaves preserve
the active draft, focus and caret. This takes effect on the next Parent process
and requires no saved-data migration. The allowance picker and custom editor are insensitive while
screen-time control is off; the saved value remains displayed. Time status uses
`GetTimeStatus` with no direct cross-account AccountsService read, and retries
temporary failures before showing unavailable.
Revocation is enabled while the form is idle when the last loaded calculated
total is positive or the broker detects running soft-blocked apps for the
selected child, including in a locked desktop with zero time. At zero time,
Parent includes `HasRunningSoftBlockedApps` in its periodic status refresh.
The grant balance itself may be zero. The broker still
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
open. The entry's public accessibility description carries the exact rejection
explanation and returns to its input guidance when edited. A wildcard rule
reaches broker validation after the dialog closes, so a
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
