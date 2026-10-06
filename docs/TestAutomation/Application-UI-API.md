# Application UI API and inventory

The running product exposes stable-ID operations on its real controls. A setter
changes the widget and uses the same selection, validation, change and activation
handlers as customer input. Automatic saves, request validation, feedback draft
updates and broker authorization remain in those ordinary paths.

Implementation: [GTK service](../../common/oh_no_parent_control_ui/application_ui.py),
[Python client](../../common/oh_no_parent_control_ui/application_ui_client.py),
[panel transport](../../child/applicationUi.js),
[GNOME adapter](../../child/gnomeApplicationUiAdapter.js), and
[rich editor adapter](../../common/oh_no_parent_control_ui/rich_editor/application_ui.js).
The [frontend design](../SystemDesign/Frontends.md#application-ui-api) owns the
component boundaries; the [UI mandate](../Mandates/UI-Automation-Mandate.MD#application-ui-api)
owns automation route selection.

## Calling the API

The Python facade supplies element references with `value` and `text` properties,
plus `getValue`, `setValue`, `getText`, `setText`, `getChoices` and `activate`.
The same operations are available to any language through session D-Bus.

```python
from common.oh_no_parent_control_ui.application_ui_client import UIClient

ui = UIClient("parent")
ui.setValue("parent-child-selector", "1001")  # Known eligible account UID.
# Wait for the selected child's public controls to become available.
ui.setValue("parent-screen-limit-toggle", True)
ui.setValue("parent-daily-limit-selector", "15m")
assert ui.getValue("parent-daily-limit-selector") == "15m"

ui.setValue("parent-daily-limit-selector", "custom")
ui.setText("parent-custom-daily-limit", "15m")
assert ui.getText("parent-custom-daily-limit") == "15"
entry = ui.getElementById("parent-custom-daily-limit")
entry.text = "30"
entry.activate()  # The normal Enter/validation path.
```

This example demonstrates input and widget readback. Completion of a setter
acknowledges input, not a completed policy save or installed customer journey.
Wait for the relevant public result before a dependent action. A loading or
busy control refuses input; setters do not silently wait and execute later.

Logical frontend names `parent`, `kiosk`, `child-request` and `child-panel`
select the endpoint and default surface inside the shared client. Product tests
import this facade and use the same IDs/operations everywhere; they do not
import adapters, detect the desktop or choose desktop-specific transports.

`getElementById` rejects missing and ambiguous IDs. Element references retain
identity and surface scope, not a widget pointer: each operation resolves the
current control. A client pins the application's unique D-Bus owner and PID;
restart requires deliberate client reconstruction. Specify `surface_id` for
normal work. Automatic scope discovery only succeeds for a unique match.

## Transport and application inventory

All implementations export `com.puffyslippers.OhNoParentControl.ApplicationUI1`.
No system-bus method, privileged helper or new background service is required.

| Surface provider | Session-bus name | Object path | Main surface ID |
| --- | --- | --- | --- |
| Parent | `com.puffyslippers.OhNoParentControl.Parent` | `/com/puffyslippers/OhNoParentControl/Parent` | `parent-window` |
| Kiosk request station | `com.puffyslippers.OhNoParentControl` | `/com/puffyslippers/OhNoParentControl` | `kiosk-request-window` |
| Child request overlay | `com.puffyslippers.OhNoParentControl.ChildRequest` | `/com/puffyslippers/OhNoParentControl/ChildRequest` | `kiosk-request-window` |
| Child GNOME panel | `com.puffyslippers.OhNoParentControl.ChildUI` | `/com/puffyslippers/OhNoParentControl/ApplicationUI` | `child-screen-time-indicator` |

`ListSurfaces() -> s` returns JSON surface metadata: `id`, `application_id`,
`type`, `visible`, `enabled`, `modal` and `parent_id`. Dialogs such as
`language-dialog`, `about-dialog`, `feedback-dialog`, `parent-revoke-dialog`
and `parent-match-rule-dialog` have their own surface scopes. Discover actual
surfaces instead of assuming a dialog already exists. Non-unique error-report
processes use `UIClient("child-request", owner=unique_owner,
object_path=exported_path)` with the actual launch-owned bus identity/path;
the consuming shared launch adapter must supply those details. Ordinary cases keep the same
facade and never infer a process from a window title or translated text.

`Call(s surface_id, s element_id, s operation, s arguments_json) -> s` accepts
a JSON object and returns a JSON value. Operation names and keys are case-sensitive.

| Operation | Arguments | Result |
| --- | --- | --- |
| `getElementById` | `{}` | Snapshot including ID, owning surface/application, logical parent ID, type/role, translated name/description, visibility, sensitivity, supported operations, and supported text/value/choices |
| `getValue` | `{}` | Canonical current value |
| `setValue` | `{"value": value}` | `null` after UI input |
| `getText` | `{}` | Current text displayed by the control |
| `setText` | `{"text": "text"}` | `null` after UI input |
| `activate` | `{}` | `null` after the ordinary activation handler |
| `close` | `{}` | `null` after the surface's ordinary close request; normal close restrictions remain |
| `getChoices` | `{}` | Finite canonical choices for a composite selector |
| `inventory` | Empty element ID; optional `offset`, `limit`, `revision` | `{"elements": [...], "next_offset": null or integer, "revision": "..."}` |

Inventory defaults to offset 0 and at most 128 elements; the maximum page size
is 256. Further pages must supply the returned revision. Changed metadata
refuses continuation, preventing an incomplete or mixed inventory from appearing
complete. `ui.getSurfaceById(...).inventory()` collects the bounded read-only
pages and rejects a changing inventory; it never replays mutations.

Runtime inventory is authoritative for constructed controls, including dynamic
app/account rows, dialogs and API aliases. The tables below inventory the stable
families and their meanings. Read a control's snapshot for its exact current
capabilities; structural containers and decorative IDs have no input methods.
Hidden controls may be inventoried but reject input. The editor's document
capabilities are refined by its element snapshot after the document is ready.

## Canonical values and portability

IDs never contain translated captions, list positions or screen coordinates.
Account choices use decimal UID strings; language choices use catalogue codes;
boolean controls use JSON booleans; policy choices use the fixed keys below.
Duration tokens use ASCII digits, `.` and `m`/`h`, independent of `LANG`,
`LC_NUMERIC` and the selected product language. `getText` returns localized
presentation; `getValue` and `getChoices` supply language-independent semantics.
Raw text entry remains literal so invalid-input validation can be exercised.

The GTK implementation uses supported GTK/GObject and session D-Bus interfaces.
It has no distro/desktop branches, AT-SPI dependency, toolkit-private field access,
window coordinates, pointer injection, focus checks or rendering acceptance.
Composite selectors operate available logical choices without opening their
popups. Clipping, covering by another window, and scroll position do not change
target identity. An inactive application page, disabled form, modal dialog or
genuinely hidden control still restricts input.
Collapsed revealer content is hidden logical state; transition progress does
not gate input. The GTK adapter uses the public
[revealer state](https://docs.gtk.org/gtk4/method.Revealer.get_reveal_child.html).

The transport consumes an adapter contract: enumerate surfaces, resolve scoped
elements, describe capabilities and dispatch finite operations. `GtkUIAdapter`
implements the GTK side without GNOME Shell imports. Panel transport consumes
`listSurfaces()`, `elements(surfaceId)` and `close()`; its GNOME adapter alone
interprets Shell session state and actors. A KDE implementation can supply a
new panel adapter behind the same `child-panel` endpoint and ID/value contract.
Applications retain toolkit/library dependencies such as GTK and GLib; these
do not require running the GNOME desktop. The normal test facade has no desktop
detection or adapter imports, and a language with its own D-Bus library can use
the wire protocol directly.

GNOME Shell is isolated in the child-panel adapter because the product's panel
extension is itself GNOME-specific. The GTK Parent and request interfaces do not
depend on that adapter. External Polkit/login prompts and operating-system file
choosers keep their provider APIs: this service neither collects passwords nor
injects attachments into application state.

## Parent controls

| ID or family | Values and operations |
| --- | --- |
| `parent-child-selector` | Get/set eligible UID string; choices are current eligible UIDs |
| `parent-child-choice-<uid>` | Actual choice buttons; use the selector setter for a closed popup |
| `parent-child-selected-<uid>` | Selected-child identity; `getText` reads the actual account-name label, excluding decorative avatar initials |
| `parent-pages` | Get/set `screen-limits` or `app-limits` |
| `parent-page-screen-limits`, `parent-page-app-limits` | Actual page toggles |
| `parent-screen-limit-toggle` | Boolean get/set; normal policy save |
| `parent-daily-limit-selector`, alias `parent-daily-limit` | Get/set offered duration such as `15m`, `60m`, or `custom`; `setText` also accepts exact offered `m`/`h` tokens; choices enumerate presets |
| `parent-custom-daily-limit` | Text/value get/set and Enter activation; both setters normalize explicit whole-minute duration tokens to digits (`15m` to `15`); ordinary 0–1439 validation remains |
| `parent-time-status` | Boolean expansion value |
| `parent-time-remaining`, `parent-time-explanation` | Public current remaining-time text and explanation |
| `parent-revoke-button` | Open ordinary revocation confirmation |
| `parent-revoke-dialog`, `parent-revoke-warning`, `parent-revoke-cancel`, `parent-revoke-confirm` | Confirmation surface, explanation and native response actions |
| `parent-app-search` | Literal search text |
| `parent-filter-match-rule`, `parent-filter-access-rule` | Get/set list of canonical category keys; choices from live selector; empty list selects none |
| `parent-filter-<kind>-<key>` | Actual filter checkbox; selector setter also works with popup closed |
| `parent-app-rows`, `parent-app-<hash>` | App collection and row metadata; row `getValue` returns the launcher ID; hash is its first 16 hex digits of SHA-256 |
| `parent-app-<hash>-access` | Get/set `allowed`, `conditional`, or `permanent` (Always Allowed, Soft Blocked, Hard Blocked) |
| `parent-app-<hash>-access-<key>` | Actual rule toggle; same autosave path |
| `parent-app-<hash>-match-rule` | `getValue` returns the current rule path/pattern communicated by the UI; activation opens the ordinary match editor |
| `parent-app-<hash>-match-pattern`, `parent-app-<hash>-match-precise` | Read the displayed match-type glyph; these are labels, with no input operations |
| `parent-match-rule-entry` | Literal editable rule text in `parent-match-rule-dialog` |
| `parent-match-rule-cancel`, `parent-match-rule-reset`, `parent-match-rule-save` | Ordinary dialog actions, including validation and save |
| `parent-legend-toggle`, `parent-time-calculation-collapse` | Ordinary disclosure actions |
| `parent-menu-button` | `getChoices`; `setValue` runs `preferences`, `help`, or `about` without a popup; `activate` opens the menu normally |
| `parent-menu-<key>`, `parent-feedback-button` | Native menu or feedback actions |
| `parent-language-loading`, `parent-language-ready`, `parent-no-users-message`, `parent-policy-warning` | Public readiness and result text/availability |
| `parent-access-denied-window`, `parent-access-denied-message`, `parent-access-denied-close` | Access-denial surface and action |

## Shared request form and language chooser

The same request IDs work in kiosk and child overlay. The fixed child selector
in an overlay remains unavailable for changing identity. Busy requests, disabled
screen-time control and absent accounts retain their existing restrictions.

| ID or family | Values and operations |
| --- | --- |
| `kiosk-child-selector`, `kiosk-approver-selector` | Get/set eligible UID string; choices are current eligible UIDs |
| `kiosk-<role>-choice-<uid>`, `kiosk-<role>-selected-<uid>` | Actual account choice and selected identity |
| `kiosk-duration-choices`, alias `kiosk-duration` | Get/set seconds string from choices, `0` for rest of day, or `custom` |
| `kiosk-duration-<seconds>`, `kiosk-duration-custom` | Actual duration radio toggle; selecting it uses the click handler, including custom-field visibility |
| `kiosk-custom-duration` | Literal minutes text; normal request validation |
| `kiosk-soft-apps-toggle` | Boolean get/set |
| `kiosk-request-submit`, `kiosk-request-cancel` | Ordinary request/cancel actions; authentication remains external |
| `kiosk-request-status`, `kiosk-screen-limit-notice` | Current estimate, progress or validation text |
| `kiosk-menu-button` | `setValue` commands `preferences`/`about`, plus `help` in overlay; preview additionally offers `change-screens`; `getChoices` reflects actual availability |
| `kiosk-menu-item-<key>` | Actual menu item action |
| `kiosk-result-title`, `kiosk-result-detail`, `kiosk-result-child-<uid>`, `kiosk-result-action` | Result readback and dismissal action |
| `kiosk-report-toggle` | Boolean error-report choice |
| `kiosk-mute-button` | Currently hidden/disabled by product policy; input refuses |
| `kiosk-language-loading`, `kiosk-language-ready`, `kiosk-language-load-error` | Public language readiness |
| `language-search` | Literal language search text in either frontend's `language-dialog` |
| `language-list` | Get/set canonical catalogue language code; choices enumerate catalogue codes; filtered-out choices refuse until search is cleared |
| `language-choice-<lowercase-code>` | Actual language radio; selection relabels the chooser |
| `language-continue`, `language-cancel`, `language-error` | Save, Cancel and ordinary save error readback |
| `preferences-tab-language`, `preferences-tab-reminders`, `preferences-close` | Request-screen preference tabs and ordinary draft cancellation |
| `preferences-tabs` | Get/set canonical active page `language` or `reminders`; `getChoices` enumerates both; setter uses the normal tab handler |
| `reminder-list` | Sorted draft records via `getValue`; stable stored reminder IDs via `getChoices` |
| `reminder-add`, `reminder-retry`, `reminder-<id>-edit`, `reminder-<id>-delete` | Normal reminder CRUD/read-retry handlers; backend remains authoritative |
| `reminder-status` | Public loading/error text while the reminder list is unavailable |
| `reminder-<id>-text`, `reminder-<id>-trigger` | Literal/default body and independently translated fixed trigger description |
| `reminder-editor-dialog` | Modal owned by the request preferences `language-dialog` |
| `reminder-text`, `reminder-value`, `reminder-unit` | Literal editor text/time; canonical unit `minute` or `second` |
| `reminder-text-count`, `reminder-duplicate-warning`, `reminder-editor-error` | Character count and normal refusal messages; duplicate seconds disable Save |
| `reminder-value-increase`, `reminder-value-decrease` | Normal bounded time increment/decrement handlers |
| `reminder-editor-save`, `reminder-editor-cancel`, `reminder-editor-close` | Save to the preferences draft or discard the current edit; no preview panel |

## Shared information and feedback

These IDs are scoped to the currently open dialog in the originating GTK app.
Kiosk restrictions continue to remove unavailable external actions.

| ID or family | Values and operations |
| --- | --- |
| `about-product-name`, `about-version`, `about-<detail>-value`, `about-integration-notice`, `about-copyright` | Read displayed information; link values expose ordinary activation when available |
| `feedback-reply-email` | Literal reply address text |
| `feedback-editor-input`, `feedback-webview` | Get/set plain editor text through Quill's user-edit path; draft and displayed document update together |
| `feedback-editor-selection` | Get/set `{"index": 0, "length": 5}` using Quill UTF-16 offsets; retained selection is independent of focus |
| `feedback-editor-document` | Read-only `getValue` returns the public Quill document delta: `{"ops": [{"insert": "text", "attributes": {}}]}`; attributes are present only when applicable. Use it for independent text, inline/block format and synthetic-link assertions |
| `feedback-editor-insert` | `setText` replaces the retained selection through Quill's ordinary user edit, preserving surrounding formatting and edit history |
| `feedback-undo`, `feedback-redo` | `activate` invokes the public Quill history action; independently read the resulting document |
| `feedback-format-style` | Get/set `normal`, `heading-1`, `heading-2`; `getChoices`; activate native picker |
| `feedback-format-normal`, `feedback-format-heading-1`, `feedback-format-heading-2` | Activate logical style alternative; boolean selection readback |
| `feedback-format-bold`, `feedback-format-italic`, `feedback-format-underline`, `feedback-format-strike`, `feedback-format-ordered`, `feedback-format-bulleted`, `feedback-format-quote`, `feedback-format-code` | Boolean current-selection formatting, boolean setter or native toolbar activation |
| `feedback-format-link`, `feedback-format-clear`, `feedback-format-attachment` | Native link/clear/attachment toolbar actions; attachment action only where offered |
| `feedback-link-target`, `feedback-link-save`, `feedback-link-remove` | Literal link input and native editing actions while the link editor is available |
| `feedback-link-editor`, `feedback-link-preview`, `feedback-format-toolbar` | Read-only document metadata/text |
| `feedback-toggle-logs`, `feedback-retry-logs`, `feedback-download-logs`, `feedback-add-files` | Normal diagnostics toggle, retry, download and chooser entry where present |
| `feedback-attachment-<key>`, `feedback-preview-availability-<key>`, `feedback-remove-attachment-<key>` | Current attachment metadata, public preview availability and removal |
| `feedback-collection-status`, `feedback-status` | Collection and submission status text |
| `feedback-privacy-link`, `feedback-privacy-text` | Open/read the in-app privacy disclosure |
| `feedback-send`, `feedback-send-without-logs`, `feedback-close` | Actual submit/close handlers; input can submit externally when deliberately invoked |
| `feedback-success-dialog`, `feedback-success-text` | Submission confirmation |
| `update-required-dialog`, `update-required-message`, `update-required-status`, `startup-error-window`, `startup-error-message`, `error-report-unavailable-dialog` | Shared startup/update/error surfaces and text; discover available response controls in inventory |

The editor bridge accepts only the fixed IDs/operations above and JSON values.
It executes packaged code; consumers cannot evaluate JavaScript, query arbitrary
DOM selectors, supply HTML or bypass attachment/submission validation. It uses
[Quill's public editing API](https://quilljs.com/docs/api) and the existing
[WebKit JavaScript bridge](https://api.pygobject.gnome.org/WebKit-6.0/class-WebView.html).

## Child panel

| ID | Values and operations |
| --- | --- |
| `child-screen-time-indicator` | Panel surface metadata |
| `child-request-button` | Open the ordinary child request overlay; translated action text |
| `child-remaining-time` | Canonical remaining seconds and localized displayed text |
| `child-request-tooltip` | Localized tooltip text |
| `child-countdown-menu` | Open the ordinary context menu |
| `child-countdown-animation-toggle` | Boolean get/set or toggle; same preference handler updates the actual menu control even without opening its popup |

Panel input refuses while locked, on the greeter, hidden, or while a request
is active. Setting the animation option changes no policy or time grant.

The read-only `child-time-notification` surface exists while the extension owns
a current system notification. IDs are stable across language and reminder
configuration changes:

| ID | Values and operations |
| --- | --- |
| `child-time-notification` | `getText`: actual notification title |
| `child-time-notification-message` | `getText`: actual plain notification body; `getValue`: configured threshold in seconds |
| `child-time-notification-urgency` | `getValue`: `critical` or `high` |

These observations expose the notification supplied to Shell, including its
current text after preference/language refresh. Logical visibility means an
owned notification on the unlocked child desktop; it does not assert that Shell
is currently presenting a banner. Native banner accessibility, dismissal and
fullscreen inhibition belong to GNOME's external provider under the
[provider exception](../Mandates/UI-Automation-Mandate.MD#target-identity-and-provider-exception).
No private Shell actor traversal or alternate product input route is provided.
Installed banner/provider qualification remains pending. The reminder
preferences dialog publishes its own guarded public IDs and normal handlers;
these read-only observations provide no settings input or backend-edit bypass.

## Reliability and lifecycle

Services verify the caller's Unix UID through D-Bus and resolve controls within
their owning application/surface. Missing, duplicate, detached and unavailable
targets refuse. Every input rechecks effective sensitivity and logical visibility;
modal child dialogs block their underlying forms. Requests, payloads, widget
walks, asynchronous callbacks and timeouts are bounded. There is no automatic
mutation retry or alternate input route after an uncertain result.

An error after input or a lost connection may leave the change applied. Observe
the public result and make a new explicit decision; do not blindly replay.
API errors contain fixed categories, not drafts, account names, addresses or
other UI contents. Calls themselves are not logged as diagnostic payloads.

Clients check ownership before every call and send it to the pinned unique bus
owner. A valid mutation acknowledgement remains successful if its handler exits
the application before the reply is decoded; it acknowledges input, not the
independently observed result. Reads also check ownership after the exchange.
Later calls refuse an exited or replaced owner, and transport failures or invalid
mutation replies remain uncertain without automatic replay.

GTK service registration follows application registration/unregistration. Shell
export follows extension enable/disable; queued authorization work is cancelled
on teardown. Editor operations wait for the existing document readiness signal
and use the normal draft bridge. New GTK processes load these APIs; packaged
child code follows the existing `session-renewal` activation classification.
No saved-data migration is needed. Finite editor API edits have explicit history
boundaries, so separate calls do not merge into one undo step based on timing.

Host UI and installed E2E tests share the
[test facade](../../tests/support/application_ui.py) and the same product client,
stable IDs and canonical operations. Their existing shared readers and worker
composites retain scenario values and independent result checks. External
authentication, system file choosers and supporting desktop tools retain their
scoped provider adapters. The [shared support guide](../../tests/support/README.md)
owns implementation reuse; the API inventory and a package build alone do not
establish installed or cross-desktop acceptance.
