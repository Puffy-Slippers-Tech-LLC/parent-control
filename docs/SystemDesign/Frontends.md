# Parent, child, and shared request UI

[System design overview](../System-Design.md)

The Parent App manages policy; the child extension presents remaining time and
opens a request overlay; the dedicated kiosk offers requests without desktop
management. Overlay and kiosk share one GTK request form.

Implementation: [Parent](../../parent/oh_no_parent_control_parent/main.py),
[child extension](../../child/extension.js),
[request application](../../kiosk/oh_no_parent_control_kiosk/main.py),
[request content](../../kiosk/oh_no_parent_control_kiosk/request_content.py),
[selector storage](../../kiosk/oh_no_parent_control_kiosk/selection_store.py).

## Main flows

- **Manage:** Parent selects a child, loads preferences, applications and time
  status, and serializes automatic saves in interaction order. App-policy saves
  can close that child's newly blocked applications across retained sessions.
  Screen-time changes use `SetParentControl`. Revocation confirms that blocked
  apps will close, lists running soft-blocked apps using catalogue names/icons,
  and stays bound to the reviewed child.
- **Session entry:** Extension startup and unlock call `PrepareOwnSession`.
  The broker restores strict app policy only for a nonzero expired grant;
  current grants and zero-duration records are no-ops.
- **Child request:** The panel opens the fullscreen shared form. `GetOwnAccount`
  fixes the child selector; submission uses `RequestOwnAccess`. Cancel/Escape
  closes the overlay; successful approval confirms for three seconds then closes.
- **Kiosk request:** The form selects eligible children and approvers and calls
  `RequestAccess`. Cancel/Escape or successful confirmation returns to sign-in.
  The kiosk GNOME session disables XDG autostart, starts its compositor, station,
  notification provider and authentication agent, and excludes Ubuntu's
  systemd-started Apport units only within that session. GNOME session-manager
  registration happens while idle; logout acknowledgement and a 750 ms exit
  deadline bound handoff, with app-unit `OnSuccess` shutdown as fallback.
  An externally cancelled logout leaves the idle form open.

Both forms require loaded accounts/preferences, an enabled screen-time toggle
and no pending request. The kiosk broker method has broader permission than
this UI guard; see [transactions](Broker.md#authorization-and-grant-transactions).
Invalid custom text leaves Request enabled but validation rejects submission
before preference saving or authentication.

Submission snapshots child, approver, duration and soft-app choice. Preference
save, authentication-agent preparation and approval callbacks belong to that
request and stage; disposed or completed requests cannot affect a later one.
Agent preparation uses the resolved language after preference saving. Destroying
the form invalidates callbacks; the broker separately owns cancellation and
[effect admission](Broker.md#request-lifetime-and-effect-admission). Language
selection and human password-entry time do not gate request lifetime.

The hidden, publicly readable desktop entry for application ID
`com.puffyslippers.OhNoParentControl.ChildRequest` supplies the overlay's dock
identity and product icon without adding an app-grid entry.

## Application UI API

Parent, request windows, shared dialogs and the child panel expose the versioned
session-bus `ApplicationUI1` protocol. The
[API reference](../TestAutomation/Application-UI-API.md) owns methods, endpoints,
canonical values and dynamic IDs.

Desktop-neutral clients call GTK/Shell adapters that use existing widgets,
signals and user handlers. Language-independent selector values survive
translation and popup changes. Page visibility, sensitivity, modal ownership,
target uniqueness and broker authorization remain authoritative. Registration
follows application lifetime. Same-user credentials, bounded operations,
owner-pinned clients and single-use mutations prevent stale input or silent
retries. Input completion does not prove a backend save.

External authentication and file choosers retain separate provider boundaries.
Arbitrary DOM selectors, supplied JavaScript, HTML injection and geometry are
not substitutes for a missing product API operation.

## Public automation identities

Stable semantic IDs also remain available to assistive technology. GTK helpers
set Builder IDs and effective disabled state; Shell helpers publish ATK IDs.
CSS/actor names and translated labels alone are not identities. Product tests
use the [Application UI API](#application-ui-api), with control inventory owned
by its reference.

Compatibility metadata includes identified window-control owners, menu/row
activation actions, mapped-window focus actions and explicit dialog owner
relations. Toolkit-generated title buttons are permitted only below the
identified `*-window-controls` owner. Validation errors appear in accessible
descriptions as well as visually.

Parent's read-only `Accessibility1.GetNativeSurfaceTransform("parent-window")`
returns a fresh GTK native offset only for one mapped, visible, active window.
It synchronizes the display and revalidates ownership before returning; it
exposes neither input nor policy. This geometry metadata is not a product-test
input route.

Dynamic account IDs use UIDs in separate child/approver namespaces. App rows use
launcher hashes with explicit state and match-rule suffixes; match dialogs also
identify their app. Feedback content exposes stable DOM IDs through WebKitGTK's
public attributes; WebKit's transient `AccessibleId` is not the DOM ID.
The finite packaged editor adapter supplies product input/readback.

Missing or incomplete observations do not prove absence. Closure requires a
fresh complete negative observation and a positive surrounding surface.
External providers require scoped ownership, ambiguity, input and result guards
under the [UI automation mandate](../Mandates/UI-Automation-Mandate.MD).

## Personal language selection

Parent/overlay load their caller's language; kiosk loads the selected child's
saved language and AccountsService desktop-language fallback. Empty preferences
open a modal chooser. Parent and request screens have separate chooser UIs,
sharing catalogue order, native names, locale resolution and search across
native/English names and IDs. Unsupported defaults resolve to English.

The chooser remains transient/modal; outside clicks and window-manager close
do not dismiss it. Selection translates the chooser privately in place.
Cancel discards the candidate and continues with the default, leaving an unset
preference to prompt next launch or kiosk child selection. Save persists through
the caller-scoped or kiosk-selected-child API before applying the new context.
Failure retains the candidate for retry. Preferences reopens the chooser.

Parent paints setup before beginning management loading, and applies saved
language before revealing content. Fatal discovery dismisses setup and shows
the startup error report; late replies cannot reopen destroyed UI.
Kiosk child changes invalidate superseded language replies. Relabeling existing
widgets preserves drafts and avoids rebuilding the form. Request controls wait
for initial setup completion. Shared dialogs inherit their owner's context.

Chooser IDs include `language-dialog`, `language-search`, `language-list`,
`language-choice-<lowercase-id>`, `language-continue` and `language-cancel`;
owning content exposes language-loading/ready state. Resolution and translation
lifecycle belong to [Localization](Localization.md).

## Parent release notes

Parent queries current-version notes asynchronously. The
[backend](State.md#whats-new-backend) owns audience, installation eligibility and
acknowledgement. Matching notes remain manually available before About even
after acknowledgement; no match hides the menu item.

Automatic presentation waits for language setup, successful account discovery
and absence of another modal. Each window attempts it once. Fatal startup or
closure invalidates late replies. Closing a successfully mapped note acknowledges
it; failed persistence retains eligibility and reports a nonfatal notice.
Querying or attempting presentation alone never consumes eligibility.

The native Markdown renderer supports headings, paragraphs, lists, quotes,
separators, fenced code, inline emphasis/code and HTTP(S) links. Raw HTML and
images remain literal and load no resources. Notes inherit the Parent context,
with versioned catalogue translation. Supplied See More links use the system
URI handler.

### Kiosk and child overlay release notes

Request surfaces use the same child audience and acknowledgement record.
Overlay uses own-account methods; kiosk uses selected-child methods.
Automatic notes wait for language setup, an idle request page and no owned
modal, with at most one attempt per child/window. Child changes dismiss old
dialogs without acknowledgement and invalidate pending reads/writes.

Continue, close or Escape acknowledges only successfully mapped notes.
Optional-note failures leave requests usable and acknowledgement failures retain
eligibility. Both surfaces share the renderer and `whats-new-*` IDs. The overlay
opens HTTP(S) links; kiosk shows labels as text and omits See More.

## Child reminder preferences

The shared preferences window has Language, Reminders and Preset Times tabs,
with persistent Cancel/Save controls. Backend lists are authoritative, including
empty lists; failed loads offer retry rather than invented defaults.
Editor Save changes a dialog draft; editor Cancel discards the edit; main
Cancel discards all unsaved changes.

Preset Times displays sorted editable durations plus locked Rest of the day
and Custom value choices. Backend bounds, uniqueness and list limits apply.
Editors accept decimal minutes/hours, reject nonnumeric, nonfinite or exponent
input, accept a trailing decimal point, and round new values half-up to one
decimal before validation. Existing whole-second values keep their precision
until edited. A removed selected preset becomes its equivalent Custom value;
an empty list retains the two fixed choices. New-duration suggestions start at
30 minutes for an empty list, otherwise the largest duration plus an hour (or
minute when necessary); duplicates cannot save.

Reminder rows sort by trigger seconds and show literal custom text or translated
default text plus trigger duration. Editors require whole minute/second values
and reject equal trigger times across units. New text is limited to 50
characters; longer existing backend text may remain unchanged while its trigger
is edited. The fullscreen switch preserves its saved value while disabled
during loading/saving or for an empty list.

Main Save writes changed presets, reminders, then language. A later failure
retains the draft and tracks earlier successful writes so retry does not repeat
them. Preset updates preserve current request/soft-app choices. Child revisions
and dialog disposal invalidate stale replies. API ownership and limits are in
[State](State.md); dialog lifetime IDs bind automation to the current draft.

Reminder Preview uses the editor's literal text or translated default, duration
and language without saving or altering real thresholds. Invalid timing disables
Preview; failures retain the edit. Previews always use Critical urgency even
when real reminders are configured to wait outside fullscreen.
Closing the editor also dismisses replies
arriving after disposal. The button temporarily indicates “See screen top”.

Ordinary child desktops use the extension's bounded
`ReminderPreview` session-bus service. It validates sender credentials, limits
text/concurrent lookups, rejects locked/greeter sessions and closes on sender
loss/disposal. Legacy preview methods remain compatible; sender-scoped IDs
prevent an old close from dismissing a newer banner. Real reminders and previews
share one slot; a threshold replaces a preview immediately.

The dedicated kiosk instead runs a bounded freedesktop notification provider
with one active banner, packaged artwork and escaped literal text. It does not
log reminder content or start in ordinary desktops. GNOME Kiosk's notification
client tag keeps its monitor-wide transparent top strip above fullscreen apps.

Both renderers share a wrapped, scalable card with product logo, discrete
one-second progress segments and Preferences/Dismiss icon actions with translated
accessible names/tooltips. They inherit desktop fonts and language fallbacks.
At delivery, 60 seconds or more uses a five-second/five-segment display; shorter
positive durations use one segment per remaining second and persist after zero
until dismissed, replaced or locked. Legacy previews without duration have no
bar. Live child balances update the bar even with custom text.

The child renderer uses owned Shell top chrome and notification models without
registering with the message tray, whose timeout cannot express this persistence.
High urgency waits outside fullscreen; Critical appears above it. The banner
follows the focused app's monitor, falling back to an active display, and
repositions without stealing focus or restarting its deadline. Visible chrome
holds one balanced Mutter unredirect inhibition; hiding, replacement, lock,
monitor loss, failure and disposal release it. Suppressed banners take no hold.
Timers, signals, actors and tooltips are disposed with their banner.

Preferences dismisses the banner and opens the existing request app's Reminders
tab, or launches the overlay with `--preferences`. Request menu/setup opens
Language. See [notification delivery](Screen-Time.md#remaining-time-notifications)
for threshold scheduling and enforcement independence.

## Localization infrastructure

[Localization](Localization.md) owns gettext contexts, language resolution,
catalogues, formatting, packaging and translation lifecycle. Language changes
preserve frontend models and in-progress work.

## Parent controls and shared information

Parent first shows blank framed sections, then checks broker permission on a
worker and reveals each section as its data becomes ready. Reactivation reuses
the window; closure invalidates late replies.

Only exact `Error.RebootRequired` opens the shared restart modal; generic errors
and global OS reboot markers do not. Parent replaces its blank window; request
forms retain ordinary exit behavior. Kiosk's available read endpoints resolve
the selected child's language before showing the notice, bypassing setup.
Repeated callbacks share one modal. Close exits without reboot; Reboot now
calls logind `Reboot(true)` as the user, preserving OS authorization/inhibitors.
Failures restore choices with a localized error; repeated activation is disabled
while pending. Only exact Parent `AccessDenied` instead shows Administrator
Required without a password challenge. Outages use startup error reporting.

Screen Limits offers 0/15/30/45-minute presets, then half-hours through 1410;
custom whole minutes are 0–1439. The backend also accepts 1440. Editing is
disabled while control is off, retaining the displayed allowance. Custom saves
debounce 350 ms and commit on Enter/focus leave; unchanged values do not save.
Draft/focus/caret survive successful saves, while interacting controls remain
serialized. Invalid edits keep the last saved value; reload clears rejected
drafts.

Keyboard preset input buffers exact `m`/`h` matches or Custom without changing
the committed choice. Enter confirms, Escape/closure/focus leave/reload discards.
An exact match clears buffered text while retaining its pending choice, allowing
another complete choice before confirmation; no rounding selects a preset.
The popup scrolls pending choices into view and keeps Custom visible. Controls
have an identified focus recipient and native popup traversal.

Parent refreshes managed accounts every five seconds, coalesces reads and keeps
selection stable. If the selected account disappears it loads the first remaining
child; empty lists show an explanation. Time status refreshes every 30 seconds.
Revoke is available when idle with positive total remaining time or running
soft-blocked apps, including zero-time locked desktops. Revocation leaves daily
allowance intact.

App Limits loads on child selection, builds rows in batches and reveals a fully
prepared table after a GTK frame. The loading mask remains fixed to the viewport.
Unlike account discovery, the catalogue does not periodically refresh:
reselection/reopening is required for added/removed launchers. Broker save-time
target resolution still uses current state. Search combines independent
multi-category match/access filters. Access changes autosave; match editing has
Save, Cancel and immediate Reset to Default.

Isolated rule-generation warnings identify affected apps, explain possible
unrestricted versions and open one error report per changed warning set while
management stays usable. Warnings refresh on selection/save/status polling.
Local app identities do not enter automatic drafts. Transient discovery errors
retry in an already-authorized window; denial and pre-authorization failure
remain closed.

Saved overrides and disappeared-launcher policy survive later visible-row saves.
Failed saves restore confirmed preferences; after irreversible termination
failure the broker may have retained stricter state, loaded on reopen.
Empty/unrelated precise rules reject locally. Basenames expand against a sole
native target directory; wildcard rejection follows broker save/report handling.
Saving the detected default or Reset clears the override.

**Known limitation:** explicit precise overrides have
`user_saved_match_rule=true` with no patterns, but restoration selects
`_default_match_rule`. For apps with suggested wildcards, reselection, reopening
or failed-save recovery displays that wildcard; a later save may persist it.
Custom wildcard overrides round-trip correctly.

Request decimals use `.` and fractional minutes round to seconds.
Denial/cancellation restores editable choices. Help and active About links are
available in Parent/overlay; kiosk remains informational. All roles can report
errors, including startup failures. Error exits initially offer reporting;
success and normal cancellation do not. Kiosk hides external/file actions.
See [feedback](Logging-and-Feedback.md#feedback-and-diagnostic-export).

Pages and About scroll on small/scaled displays. Allowance/filter popovers fit
available space; allowance chooses the roomier side and keeps Custom fixed.
The App Limits legend wraps, closes explicitly or on outside click, and retains
its existing boolean API.

## Child panel preference

The primary panel action opens one overlay. Its tooltip explains remaining time
and primary/context actions. The child-owned
`one-minute-countdown-animation` GSettings boolean defaults false, applies
immediately and survives login/reboot. It controls final-minute flashing and
final-ten-second rotation, with no policy or request-media authority. There is
no separate child settings window.

## Responsive request layout

Both surfaces use GTK monitor scaling with a 14-pixel logical base font.
Screen dimensions do not introduce another zoom. The gateway uses up to 40%
of desktop width; through 1200 logical pixels of height its/form preferred widths
cap at 640/384, then grow proportionally with height. Narrow windows preserve
readable controls and fit form content into the opening.

Backdrop bands fit independently; scenery uses uniform scaling and anchored
bases rather than stretching silhouettes. Lightning follows the same transforms.
Chains share a coarse pixel grid with nearest-neighbour enlargement.
Duration choices reflow into one/two columns, account labels stack as needed,
and wrapped text/vertical scrolling retain corner controls and stationary frames.
External scrollbar allocation follows the projected viewport so its input target
matches its visible track. Results share the same sizing/overflow container.

Development previews use real disposable Mutter surfaces/scales on an explicit
private bus, leaving host displays and saved data unchanged. Their viewer/input
support is a manual review aid, not an automation or installed-acceptance route.
Child previews require GNOME Shell 50 and isolated payload/presentation state.
Production extension changes require package activation and session renewal.

Package staging precomputes fixed lava RGBA treatments with a version/dimension/
source-digest bound cache and exact-length decoding. Missing/damaged/stale caches
fall back to the original calculation, including edited checkout previews.

## Lightning audio

Sound/lightning are currently disabled through `REQUEST_MEDIA_ENABLED`; the
mute control is hidden/insensitive and audio import/synthesis/pipeline creation
is skipped. Separate saved per-child/surface mute values remain compatible.

When enabled, generated thunder follows visible flashes, gain and stereo
position through short GStreamer PCM buffers; missed flashes are not replayed.
Mute flushes playback, unmute waits for a fresh flash, successful dismissal fades
tails and destruction releases the pipeline. Missing audio never blocks requests.
Logs contain fixed state/error codes, excluding device names/debug text.

## Remaining-time explanations

The shared duration formatter preserves partial minutes with seconds and uses
compact hours/minutes. Parent always shows daily remaining, grant remaining and
their maximum, including zero operands. With control off, zero daily/total is
not itself an access restriction.

Fixed request estimates query `GetTimeStatus` with additional seconds.
Interactive changes debounce 250 ms; completed preference/approver loads queue
immediately. Reads are asynchronous/serialized, discard superseded replies and
refresh every 30 idle seconds. Rest-of-day says until midnight. Higher-priority
validation/loading/approval messages win. Estimate failure never blocks submission;
approval recalculates the real grant. Disposal removes timers and invalidates reads.

## Request-selector state

Non-authoritative selector defaults live in each requesting OS user's
`$XDG_STATE_HOME/oh-no-parent-control/request-selections.json`. Kiosk remembers
child/approver; overlay fixes its own child and remembers approver. Saved UIDs
must remain eligible, otherwise the first current account is selected.
Production local approver choice wins over broker preferences, including late
loads; absent local choice does not restore the broker's saved approver.
Previews have no local store and may read that field without persisting it.

Duration, custom value/unit and soft-app choice belong to the shared per-child
record. Mute values remain separate per surface but inactive while media is off.
Custom Minutes/Hours radio choices reflow with translated labels, retain entered
values across language changes and persist through the existing request-choice
path. The API keeps canonical `minutes`/`hours` values; Escape uses the form's
normal exit action.

## Related design

- [Broker permissions](Broker.md#broker-interface-and-roles) and
  [grant transactions](Broker.md#authorization-and-grant-transactions).
- [Countdown/enforcement](Screen-Time.md#countdown-and-expiry-enforcement),
  [saved state](State.md) and [kiosk confinement](Kiosk-Confinement.md).
- [Feedback](Logging-and-Feedback.md#feedback-and-diagnostic-export) and
  [startup lifecycle](Lifecycle.md#startup-login-and-update-lifecycle).
