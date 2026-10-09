# Persistent and derived state

[System design overview](../System-Design.md)

Read this for data ownership, preference/configuration schemas, defaults,
and saved-data changes.

Implementation: [preferences.py](../../broker/oh_no_parent_control/preferences.py), [config.py](../../broker/oh_no_parent_control/config.py), [configuration example](../../config).

## Persistent and derived state

The child GSettings schema also holds a non-authoritative, user-local
`wellbeing-banner-backup` recovery string: empty when inactive, otherwise
`default`, `true` or `false`. The unprivileged session service alone owns this
record and the temporary single-key override described in
[native banner suppression](Screen-Time.md#native-wellbeing-banner-suppression).
It contains no identity or policy data and changes no broker preference format.

The single product preference source for user UID `N` is:

```text
/var/lib/oh-no-parent-control/preferences/N.json
```

The preference directory is root-only and each mode-`0600` record is validated
and atomically replaced. The current preference format is version 4 (`FORMAT_VERSION` in
`preferences.py`); its logical schema is:

```text
version
personal = { language, notifications = { show_in_fullscreen, reminders[] }, time_grant_presets[], whats_new_seen[]? }
parent_control_enabled
daily_time_limit_minutes
apps[desktop-id] = {
    state, targets[], patterns[], user_saved_match_rule
}
request = {
    last_selected_duration, last_custom_minutes,
    allow_soft_blocked_apps, last_selected_approver_uid,
    kiosk_muted, child_muted
}
```

App states are `allowed`, `permanent` (hard blocked), and `conditional` (soft
blocked). Normalization omits an allowed entry unless it carries a saved match
rule that must survive later policy changes.
This is a storage guarantee. The current Parent restoration path has a
[precise-override display limitation](Frontends.md#parent-controls-and-shared-information)
for apps with a suggested wildcard.

Machine configuration is separate at
`/etc/oh-no-parent-control/config.json`. It contains only its schema version,
the kiosk UID, and the minimum successful-request interval; it does not
duplicate child preferences.

Language uses the same `PreferenceStore`, directory, per-user record,
validation, atomic writer and package migration chain as policy and request
settings. Version 4 adds a `personal` section containing `language`. The
`3 -> 4` migration retains all policy and request choices and adds an empty
language; direct upgrades from versions 1 and 2 run every intermediate step.

A personal-only account's on-disk record contains `version` and `personal`,
without policy fields. Reads normalize missing policy to the usual defaults.
A policy save writes the full record and retains the latest personal settings.
This distinction preserves policy ownership for migrated child records while
excluding language-only accounts from uninstall enforcement cleanup. Root,
administrator and kiosk language records use this same infrastructure; they
do not require a separate settings directory or data family.

The mode-`0700` directory and mode-`0600` records remain root-private. The
shared writer flushes the file and directory before success. Missing records
use defaults. Duplicate keys, invalid records and unsupported schema versions
are rejected; language saves never replace them.

`GetOwnLanguage()` returns a string; `SetOwnLanguage(language)` persists and
returns that string. Both derive the account from bus credentials and accept no
target UID. Administrators (including root), eligible children and the configured
kiosk account may use them. The own-language methods always address the caller.
Parent uses its administrator's selection, the child extension and overlay
share the child's selection, and the kiosk uses the selected child's selection,
independent of its approver. `GetChildLanguage(target_uid)` and
`SetChildLanguage(target_uid, language)` are restricted to the configured kiosk
caller and an eligible child target. They read and write the same personal record,
with the same validation and persistence guarantees as the own-language methods.

`GetChildLanguageContext(target_uid)` returns the saved string and the child's
AccountsService desktop language without persisting a default. It retains the
same kiosk-caller and eligible-target authorization.

An empty string means follow the frontend session's language, or the selected
child's desktop language in kiosk; the broker does
not resolve its root process locale. Explicit IDs contain a 2–8 ASCII-letter
language followed by optional hyphen-separated 1–8 ASCII-alphanumeric subtags,
with at most 63 characters in total (for example `en`, `pt-BR`, `zh-Hans`). IDs
are preserved as supplied. POSIX locale strings, paths and colon-separated
language lists are rejected. Storage validates syntax, not translation
availability. The shared [language catalogue](../../common/oh_no_parent_control_ui/languages.json)
owns the ordered supported choices and native display names for all components;
the Python loader is GTK-independent and the same JSON is packaged with the
Shell extension. Frontends own locale resolution and translation application.
There is no change notification in this API.

Child reminder preferences are an optional, backward-compatible version-4
personal field. Older records normalize an absent `notifications` field to
`show_in_fullscreen = true` and four reminders: 10 minutes, 5 minutes, 1 minute
and 15 seconds, each with empty text. Explicit lists, including an empty list,
are authoritative; reads and upgrades never merge presets into saved lists.
No schema increment or released migration change is needed for this optional
field under the [migration compatibility rule](Data-Migration.md#adding-a-preference-migration).

`GetOwnNotifications()` returns the configuration as JSON.
`SetOwnNotifications(notifications_json)` atomically replaces it and returns
the normalized saved JSON. Both derive the target from bus credentials and
require an eligible child; administrators and the kiosk cannot use them for
another account. `GetChildNotifications(target_uid)` and
`SetChildNotifications(target_uid, notifications_json)` expose the same data
only to the configured kiosk for an eligible selected child. This whole-list replacement supports dialog create,
read, update and delete operations without a separate data family. Each record
has a stable `id`, positive integer `value`, `unit` (`minute` or `second`) and
optional `text` (normalized to empty when omitted or whitespace-only).
Nonblank custom text is preserved literally. The configuration has at most 64
records with unique lowercase hyphenated IDs of at most 64 characters; durations
fit uint32 seconds and text has at most 4096 Unicode characters, without NUL
or surrogate code points. The JSON transport is bounded at 512 KiB and rejects
duplicate keys. Rejected inputs never replace saved data.

Notification writes use the same locked read/modify/write, mode-0600 atomic
replacement and fsync path as language. They preserve language, policy and
request choices, and policy commits/rollback retain the latest notifications.
Personal-only records remain personal-only. No notification write changes
AccountsService, grants or enforcement. The shared request-screen
[preferences dialog](Frontends.md#child-reminder-preferences) manages the list.

Language writes preserve policy and request settings. The store serializes
language read/modify/write with policy commits; policy saves and rollback retain
the current personal settings even when given a stale snapshot. `SetPreferences`
cannot change a child's personal settings. Personal changes are excluded from
approval-policy snapshot comparisons. Language writes do not alter
AccountsService, OS locale settings or grants. Ordinary removal
retains these records; purge removes them with the product state directory.
The [language selectors](Frontends.md#personal-language-selection) use this API.
[Localization](Localization.md) defines translation contexts and language
application without changing persistence, authorization or policy ownership.

## Time grant preset backend

`personal.time_grant_presets` is an optional, compatible version-4 field.
Absent means the shipped durations: 300, 900, 1800, 3600, 7200 and 14400
seconds. A saved list replaces those defaults completely, including an empty
list. Reads and writes normalize it into ascending numeric order. There may be
at most 64 unique whole-second durations from 6 through 86400, derived from
the shared Custom value range of 0.1 through 1440 minutes. Booleans, fractional seconds, duplicates and invalid
values are rejected before persistence.

`GetOwnTimeGrantPresets()` and `SetOwnTimeGrantPresets(presets_json)` address
only the eligible child identified by bus credentials.
`GetChildTimeGrantPresets(target_uid)` and
`SetChildTimeGrantPresets(target_uid, presets_json)` require the configured
kiosk caller and an eligible selected child. Each method returns the normalized
JSON array of editable durations in seconds; setters accept that same array.
Whole-list replacement supports create, read, update and delete. Transport is
bounded at 512 KiB and rejects duplicate JSON keys and excessive nesting.

Rest of the day (`"0"`) and Custom value (`"custom"`) are fixed selector
choices outside the editable array. They cannot be inserted, edited or deleted
through this API. The backend `time_grant_choices()` helper appends both to
the sorted editable choices, including when the array is empty. Remembered
`request.last_selected_duration` accepts either fixed choice or a canonical
decimal string within the fixed-duration bounds. It remains valid if a preset
is later deleted; preset edits do not rewrite remembered requests or change
grant authorization or arithmetic.

Writes use the existing locked read/modify/write and atomic mode-0600,
file/directory-fsynced persistence. They preserve language, reminders, release
acknowledgements, policy and request choices. Stale policy commits and rollback
retain the latest preset list; personal-only records remain personal-only.
Reads do not create files. Saved customizations and empty lists survive broker
restarts and migration retries without merging defaults. Ordinary removal
retains them; purge removes them with the preference directory.

The shared request form reads this field from `GetPreferences`, and its
[Preset Times tab](Frontends.md#child-reminder-preferences) edits the same list
through these APIs. Request choices use the backend helper and range definitions.
Broker changes activate on process restart and frontend changes on a new request
process; no schema increment or released migration edit is required.

## What's New backend

The broker reads Parent notes from the matching release section in
[`VersionHistory.md`](../VersionHistory.md), installed at
`/usr/share/oh-no-parent-control/VersionHistory.md`. A `## v<version>` heading
with an optional draft separator or date starts each release. The following
Markdown body is preserved literally, excluding the release heading, until the
next release heading. Release-like headings inside fenced code are content.

Kiosk and child overlay notes come from
[`whats-new-child.toml`](../../data/whats-new-child.toml), installed at
`/usr/share/oh-no-parent-control/whats-new-child.toml`. Authors edit TOML with a
top-level `version = 1` and at most one `[[records]]` block per release.
Each record requires `ProductVersion` and `Content`; `SeeMore` is optional.
The source determines the audience; there is no `ShowIn` field. For example:

```toml
version = 1

[[records]]
ProductVersion = "1.4"
SeeMore = "https://example.com/releases/1.4"
Content = '''
## New features

- **Formatted** release notes
'''
```

Type Markdown with normal line breaks inside the triple-single-quoted literal
string. Quotes and backslashes need no escaping; TOML removes the first newline
after the opening delimiter and preserves subsequent whitespace. Three
consecutive single quotes delimit the string and cannot occur inside it; use a
triple-double-quoted TOML string with TOML escaping if that content is needed.
For an empty catalogue, use `version = 1` and `records = []`.

Versions are numeric dotted product versions, independent of DEB/RPM revisions.
Comparison is numeric (`1.10` follows `1.9`); trailing zero components normalize
(`1.4.0` equals `1.4`). Duplicate versions within either source are rejected.
The child catalogue may omit the installed version; this returns no child notes,
without falling back to Parent notes or an older child release. Duplicate TOML
keys, missing required fields, unknown
fields, empty content and unsafe SeeMore URLs are rejected. SeeMore accepts
absolute ASCII HTTP(S) links without credentials, backslashes or percent-encoded
authorities; bracketed IP addresses must occupy the complete host. Percent escapes
in paths, queries and fragments are preserved. The document is bounded at 512 KiB,
64 records, 65,536 content characters per record and 2,048 URL characters.

The API returns JSON and preserves Markdown content literally. The
[frontends](Frontends.md#parent-release-notes) own translated rendering and link
actions; the dedicated kiosk omits external launches.

`GetOwnWhatsNew()` and `AcknowledgeOwnWhatsNew(product_version)` derive the UID
from bus credentials. Administrators (including root) receive Parent records;
eligible children receive Child records. The kiosk uses
`GetChildWhatsNew(target_uid)` and
`AcknowledgeChildWhatsNew(target_uid, product_version)` for an eligible selected
child. Those two methods are kiosk-only. Kiosk and child overlay therefore share
the child's acknowledgement; the approver's account is independent.

All four methods return JSON with `product_version` and `records`. Each returned
record includes the validated metadata, a derived `record_id` and `auto_show`.
Only records matching the installed version and caller's component are returned.
Users who skip a release never receive its old notes. Previously acknowledged
current records remain in this result for manual menu access, with
`auto_show = false`. A fresh installation also sets `auto_show = false`; an
upgrade from a lower version sets it true for unseen current records. Installation
origin is recorded during [package configuration](Data-Migration.md#whats-new-installation-history),
so this decision works even when a user never opened the old app.

The stable record identity combines canonical version and source audience, such as
`1.4:Parent` or `1.4:Child`. Parent and Child records at the same
version have independent acknowledgements, including if a UID's role changes.
Editing content or SeeMore preserves identity. Former combined `Child,Parent`
acknowledgements remain valid for both audiences and are retained while either
source still contains that version. Acknowledge selects the unique current
record for the caller's component and supplied version; past, future, unknown and
wrong-component records are refused. Frontends must acknowledge after successful
display/close, including manual opening, and persist successfully before treating
the record as seen. Querying alone does not consume eligibility.

`personal.whats_new_seen` is an optional compatible version-4 field; absent means
no acknowledgements. It contains at most 256 unique record IDs. The store merges
acknowledgements under its existing write lock and atomically writes the record.
Every successful acknowledgement also removes IDs absent from the complete
packaged metadata, retaining IDs for other components and older metadata that
still exists. Queries do not collect garbage. Language, reminders, request choices
and policy remain intact; policy saves and rollback retain the latest personal
state. Personal-only records remain personal-only. Ordinary removal retains
acknowledgements; purge removes them with product state.

The ownership of runtime state is deliberately split:

| State | Authority | Purpose |
| --- | --- | --- |
| Personal language selection | Product preference record, `personal.language` | Per-user presentation intent |
| Configured screen-time and app choices | Product preference record | Durable parent intent |
| `AppFilter` | AccountsService | Live launcher/Flatpak blocklist derived from preferences |
| `ActiveExtension` | AccountsService | Current one-time grant |
| Usage intervals and estimates | `malcontent-timerd` | Measured daily use |
| UID-scoped native deny rules | fapolicyd | Live execution policy derived from `AppFilter` and saved patterns |
| Extension payload | System GNOME data directory | Immutable package content discovered when Shell starts |
| Extension activation | Per-account GNOME settings | Derived enabled state for managed children |
| Request selector defaults | Requesting user's XDG state directory | Last kiosk child/approver or child-overlay approver; validated against current lists |
| Countdown-animation preference | Child user's GSettings database | Personal panel preference, default false; no time or app-policy authority |
| Feedback draft, selected file bytes and retries | Frontend process memory | Optional report composition; no persistent outbox |
| Structured diagnostic history | Broker-owned component event files | Bounded approved events, independent of child preferences |

No measured usage, grant expiry, or generated execution state is imported into
the preference record.

A missing child record loads validated defaults; a record is created on save.
Defaults disable screen-time control, set a zero daily limit, leave apps allowed,
and select a 30-minute request with a 0.1-minute custom value, soft apps blocked,
no saved approver, and both surfaces muted.
The current validator normalizes omitted optional request fields and an omitted
daily limit.

Preference/API daily limits allow 0–1440 whole minutes; the Parent App editor
currently accepts 0–1439. Request custom durations separately accept 0.1–1440
minutes. The saved approver and mute fields remain supported, but production
selector restoration prefers user-local state and request media is disabled.
See [request selectors](Frontends.md#request-selector-state).

The child panel's `one-minute-countdown-animation` boolean belongs to schema
`com.puffyslippers.oh-no-parent-control.child`, not the root-owned JSON record.
It survives disable/re-enable and is independent of `request.child_muted` and
`request.kiosk_muted`. Product removal removes extension activation entries,
not this preference; purge also leaves ordinary users' selector files and
GSettings databases alone. Preference migration does not migrate those UI stores.

Broker startup reconciles the current live app filters and enabled extension
state; it does not replay all preference values into AccountsService. In
particular, ordinary package removal clears derived restrictions while retaining
preferences. Reinstallation preserves those choices without automatically
reconstructing every cleared runtime limit/filter or one-time grant.

The machine configuration also currently uses version 3, independently of the
preference schema. Its example kiosk UID is not a fixed runtime identity;
installation generates the actual value.

## Related design

- For non-authoritative per-user selector state, read [Front ends](Frontends.md#request-selector-state).
- For projecting app preferences into live enforcement, read [filters and execution rules](Applications.md#live-filter-and-execution-rules).
- Before shipping incompatible readers or writers, follow [Data migration](Data-Migration.md#adding-a-preference-migration).
