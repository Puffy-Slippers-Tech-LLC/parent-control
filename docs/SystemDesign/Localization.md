# Localization

[System design overview](../System-Design.md)

This module defines the localization infrastructure, per-user language backend,
language settings GUI, and translation lifecycle across Parent, the child panel,
the child request overlay and the dedicated kiosk. The
[specification](../Specification.md) owns customer behavior;
[State](State.md#persistent-and-derived-state) owns persistence and
[Front ends](Frontends.md#personal-language-selection) owns the chooser surfaces.

Implementation entry points: [localization.py](../../common/oh_no_parent_control_ui/localization.py),
[shared source messages](../../common/oh_no_parent_control_ui/messages.py),
[deferred messages](../../common/oh_no_parent_control_ui/message.py),
[GTK bindings](../../common/oh_no_parent_control_ui/translation_widgets.py),
[Shell translation context](../../child/localization.js),
[MO decoder](../../child/gettext.mjs),
[languages.py](../../common/oh_no_parent_control_ui/languages.py),
[language catalogue](../../common/oh_no_parent_control_ui/languages.json),
[preferences.py](../../broker/oh_no_parent_control/preferences.py),
[broker core](../../broker/oh_no_parent_control/core.py),
[D-Bus service](../../broker/oh_no_parent_control/service.py),
[Parent chooser](../../parent/oh_no_parent_control_parent/language_dialog.py),
[request chooser](../../kiosk/oh_no_parent_control_kiosk/language_dialog.py),
and [Makefile](../../Makefile).

## Responsibilities and language ownership

Language is a personal presentation preference belonging to the operating-system
account running the surface. It does not follow the child selected in Parent or
the approver selected in a request form.

| Surface | Language owner | Selection UI |
| --- | --- | --- |
| Parent App | Signed-in administrator | Parent Preferences |
| Child Shell panel | Signed-in child | Preferences in the child request overlay |
| Child request overlay | Same child as the panel | Request Preferences |
| Dedicated kiosk | Kiosk account | Request Preferences |
| Shared About, feedback and error windows | Owning frontend account | Inherit the frontend translation context |

The broker authenticates the caller and stores language intent. Frontends resolve
that intent against the language catalogue, load message catalogues and render
text. The broker never chooses a language from its own root-session environment
or translates policy, protocol values or diagnostics.

All normal localization works offline. Catalogues are trusted package assets,
with no runtime download, remote translation service or user-supplied catalogue.
Changing language changes presentation; it does not modify grants, limits,
application policy, accounts or operating-system language settings.

## Localization infrastructure

### Language catalogue and resolution

The shared JSON catalogue owns ordered product language IDs and their native
display names. Python reads it without GTK; the same JSON is packaged with the
Shell extension. Native names remain recognizable regardless of the active UI
language and are not translated into that language.

| Product ID | Native name | Gettext locale directory |
| --- | --- | --- |
| `en` | English | `en` |
| `de` | Deutsch | `de` |
| `es` | Español | `es` |
| `fr` | Français | `fr` |
| `pt-BR` | Português (Brasil) | `pt_BR` |
| `zh-Hans` | 中文（简体） | `zh_Hans` |
| `ru` | Русский | `ru` |
| `it` | Italiano | `it` |
| `pl` | Polski | `pl` |
| `ja` | 日本語 | `ja` |

Resolution uses the saved language when nonempty. An empty value uses the primary
frontend session message language, supplied by `GLib.get_language_names()` for
GTK. An unsupported primary language resolves to English, rather than searching
later session-language entries. A nonempty unsupported saved ID also resolves to
English and remains preserved in storage. With no frontend session language
supplied, resolution defaults to English.

Regional and script variants collapse by base language to the single product
choice. For example, `fr-CA` resolves to `fr`, Portuguese variants resolve to
`pt-BR`, and Chinese variants resolve to `zh-Hans`. This is an explicit catalogue
policy, including the choice of Simplified Chinese. Supporting separate regional
or script translations requires updating the resolver and catalogue together.

Product IDs use hyphens; gettext directories use underscores. Only resolved
catalogue IDs become filesystem search components. Saved values and locale
environment strings are never used directly as paths. Selection availability
and individual message coverage are separate: an absent translated message
falls back to its English source without rewriting the user's preference.

### Translation context

The domain is `oh-no-parent-control`. The GTK-independent Python loader exposes:

```python
translations = load_translations(saved_language, GLib.get_language_names())
_ = translations.gettext
ngettext = translations.ngettext
pgettext = translations.pgettext
npgettext = translations.npgettext
```

Each frontend owns its translation object and passes the context to shared UI.
Shared presentation helpers retain source messages and named operands until the
destination renders them through its owning context. Translation
methods are bound in the owning scope, rather than installed globally in
`builtins`. The application does not mutate `LANGUAGE`, `LANG`, `LC_MESSAGES` or
`LC_ALL`, or call process-wide `setlocale` to apply a personal selection.

The loader uses standard-library GNU gettext support. Missing catalogues or
entries return English source messages, including English plural fallback.
Unreadable or malformed catalogues surface as package errors; they are distinct
from ordinary incomplete translation coverage.

The child Shell adapter follows the same resolution and lookup contract and
reads the same MO domain. It selects the catalogue explicitly, because the
child's product preference can differ from the GNOME session language. Its
translation context is private to the extension; it does not alter Shell's
process locale or another extension's text domain.

For explicit catalogue lookup, the GJS adapter reads package bytes through Gio
and decodes GNU MO messages, contexts and plural metadata. The decoder validates
the header, endianness, string-table bounds and UTF-8 text. Plural expressions
use a bounded parser for gettext's integer-expression grammar, never JavaScript
`eval`; counts and resulting form indexes are checked. Python and GJS use common
catalogue fixtures to verify identical lookup and fallback results. There is one
translation source format, not a separate JavaScript message dictionary.

### Message authoring

English source strings are complete literal messages in the shared
`common/oh_no_parent_control_ui/messages.py` module. Parent, request, shared
dialogs and the rich editor refer to its named messages. The Shell build exports
these same messages to a generated `messages.json` asset; it does not maintain
another hand-written source dictionary. Add or edit a message in this module,
update the POT and the affected PO entries, then rebuild the packaged assets.

Extraction recognizes explicitly marked `_`, `gettext`, `ngettext`, `pgettext`
and `npgettext` calls. Messages use named placeholders and interpolation occurs
after translation:

```python
greeting = _("Hello, %(name)s") % {"name": display_name}
remaining = ngettext("%(count)d minute", "%(count)d minutes", count) % {"count": count}
action = pgettext("button action", "Open")
```

Do not extract f-strings, concatenate sentence fragments, or translate user
content. Use plural methods instead of English singular/plural conditionals and
context for ambiguous short labels. `# Translators:` comments explain placeholders,
meaning and layout constraints. JavaScript uses the corresponding extraction
keywords and named-placeholder contract.

Markup and rich-editor content require destination-specific escaping of dynamic
values after translation. Translation is not an HTML or Pango escaping step.
Catalogue checks retain required placeholders; shared format helpers reject
invalid substitutions rather than presenting damaged policy explanations.

GTK text and accessibility bindings retain the source message and model operands.
They render through the owning window's context and relabel existing controls
when it changes. Binding records follow native GObject lifetime, survive Python
wrapper collection, move between contexts on reparenting, and leave the registry
when the native object is finalized. Shared dialogs inherit their transient
parent's context. Rich editor labels are updated in the existing document,
preserving its content and undo state. Product branding remains exactly `Oh No! Parent Control` in every
language; account names, paths and other user data are not message identifiers.

## Language user settings backend

The language lives in `personal.language` in the root-owned UID record at
`/var/lib/oh-no-parent-control/preferences/<uid>.json`. It uses the same
`PreferenceStore`, validation, atomic writer and migration chain as child policy
and request choices. There is no separate language file or per-frontend copy.
The exact schema and ownership contract remain in [State](State.md).

| D-Bus method | Input | Result | Account boundary |
| --- | --- | --- | --- |
| `GetOwnLanguage` | None | Saved language string | Caller UID from bus credentials |
| `SetOwnLanguage` | Language string | Persisted language string | Caller UID from bus credentials |

These methods accept no target UID. Administrators, including root, eligible
children and the configured kiosk account may access their own language.
Authorization occurs before storage access; syntax validation occurs before a
write. Parent's policy-editing authority does not grant a method for changing
another account's personal language. See [broker permissions](Broker.md#broker-interface-and-roles).

Empty means follow the frontend session language. Explicit IDs contain 2–8 ASCII
letters followed by optional hyphen-separated 1–8 ASCII-alphanumeric subtags,
with a maximum total length of 63 characters. Values are preserved as supplied.
POSIX locale strings such as `en_US.UTF-8`, paths and colon-separated language
lists are rejected. Storage checks syntax independently of catalogue availability
so package changes do not discard valid saved intent.

Personal-only records contain `version` and `personal`, and do not claim that
the account has managed child policy. Policy reads normalize absent policy
fields to defaults. Language writes preserve policy and request fields; policy
saves and rollback preserve the latest personal selection even when given stale
snapshots. The store's write lock serializes these record replacements.
Personal changes do not invalidate approval-policy snapshot comparisons.

The preference directory is mode `0700`, records are mode `0600`, and successful
writes flush both file and directory around atomic replacement. Invalid,
duplicate-key or future-version records are rejected, never replaced by defaults.
The caller receives success only after persistence succeeds. A save error must
not cause the GUI to claim a new selection was committed.

Version 4 includes the personal section; the `3 -> 4` migration adds an empty
language while preserving policy and request values. Direct upgrades run the
intermediate migrations. Changes to the meaning or shape of saved language state
follow [Data migration](Data-Migration.md). Ordinary removal retains personal
records; purge removes them with product state. Personal-only records are
excluded from enforcement cleanup.

## Language user settings GUI

Parent, kiosk and child overlay read their own language asynchronously at startup.
A nonempty saved value bypasses the chooser. An empty value opens a modal chooser
with the resolved primary session language selected. The chooser displays native
language names in catalogue order and explains that Preferences can change the
selection, using the same neutral wording for initial setup and subsequent visits.

Parent uses its native GTK dialog; the kiosk and overlay share their separate
metal-board dialog. Both share catalogue and resolution logic. Continue is the
sole dismissal action and commits the selected explicit product ID through
`SetOwnLanguage` before closing. Saving disables the choices and Continue to
prevent duplicate submissions. A failure retains the choice, displays an error
and enables retry.

The top-right Preferences action reopens the chooser with the account's saved
selection. Opening it does not write a default. Selecting a language changes only
the dialog's candidate value; Continue commits it. The candidate does not preview
translations or replace the active context before persistence succeeds.

The empty storage value supplies the first-run default; the chooser's Continue
action makes the selection explicit. The chooser exposes explicit product
language choices. Empty remains the unset state that triggers setup at frontend
start, rather than a selectable persistent mode.

Request controls wait for startup language setup. Load failures are visibly
reported and Preferences retries the read; failure is not treated as an empty
preference or a successful setup. Language setup neither authenticates an approver
nor submits a request. Parent management and request readiness remain governed by
their existing policy and account checks.

The [frontend contract](Frontends.md#personal-language-selection) owns public
chooser IDs and readiness observations. `language-dialog`,
`language-choice-<lowercase-id>` and `language-continue` stay stable across
translations. Accessible names, descriptions and validation messages are
translated for people; IDs, actions and selected-value identities are not.

## Translation lifecycle and shared UI

At startup the frontend establishes its translation context from the saved value
before presenting the main translated content. The initial chooser uses the
resolved session context. Startup notices that precede a successful language
read use the session context, with English source fallback.

After a successful language save, the frontend loads a new translation object
and relabels its owned surface and open shared dialogs. Bound methods from the
old object do not change automatically. If loading the new catalogue fails, the
saved preference remains authoritative; the surface retains its last usable
context and reports the catalogue error without claiming application succeeded.

Relabeling preserves account selections, unsaved numeric input, focus, scroll
position, policy-save queues, request state and feedback drafts. It does not
recreate workers, timers or authentication transactions. Dynamic labels render
from their underlying model values through the active context. Asynchronous
results carry data or stable error categories rather than already translated
sentences, so late replies use the current language.

There is no language-change signal in the D-Bus contract. Each GTK frontend
refreshes the saved value when opening Preferences; other running windows refresh
at their next such interaction or process start. The child panel reloads its own
language on enable, on session resume and after its request overlay exits. This
keeps panel and overlay tied to one child preference without requiring a broker
broadcast. These reads must not delay countdown calculation or expiry locking.

About, help labels, feedback controls, validation, request results and user-facing
error explanations inherit the caller's context. Error categories and diagnostic
payloads stay stable. User-written reports, account names, filenames and external
application names remain data. Product locale does not relabel the desktop's
application catalogue, GDM, Polkit authentication dialog or other system-owned UI.

## Formatting, layout and accessibility

Language selects message presentation. It does not change time zones, midnight
boundaries, grant arithmetic, usage measurement or the numeric values exchanged
with the broker. Duration labels use shared localized units and plural rules;
input validation retains the established numeric contract rather than silently
changing decimal syntax with UI language.

Whole-hour durations use gettext integer plural rules. Fractional hours have
separate catalogue messages so Russian and Polish decimal forms do not inherit
the form for integer five. A context for fractions below two retains the French
and Brazilian Portuguese singular. Attachment-size units are catalogue messages
too; language changes retain the existing byte thresholds, scale and numeric value.
Error-report explanatory text is rendered through the owning dialog's context
once when the editable draft is seeded; later language changes preserve that
draft. Rich-editor link actions show Edit link in preview mode and Save link
in editing mode, updating their visible and accessible labels together.

Labels wrap and containers scroll at supported display sizes and scales. Layout
uses start/end alignment and text direction rather than assuming left/right
reading order. Long translations, CJK glyphs, non-ASCII account names and mixed
direction data must retain usable controls and correct accessible text. Font
fallback supplies missing script glyphs; the request screen's decorative font
must not make translated text illegible.

Images and branding remain language-neutral; instructions and results are widget
text rather than text baked into artwork. Keyboard navigation and public control
IDs remain stable. Screen-reader labels and descriptions are updated alongside
visible labels. RTL catalogue additions also require direction and layout review,
not just a new JSON entry.

## Catalogue workflow and packaging

The [Makefile](../../Makefile) owns extraction, validation, compilation and the
installed payload. GNU gettext is a build dependency for both Debian and RPM.

| Operation | Contract |
| --- | --- |
| `make update-pot` | Extract marked production Python and child JavaScript messages into `po/oh-no-parent-control.pot`; exclude broker, tests, previews and vendored editor code |
| `msginit` / `msgmerge --update` | Create or update `po/<locale>.po` using canonical underscore locale names and the correct language-specific `Plural-Forms` header |
| `make check-translations` | Validate PO syntax, headers and marked placeholders with `msgfmt --check --check-format` |
| `make translations` | Compile MO files under the checkout's shared Python `locale/` directory; `LOCALE_OUTPUT` selects another output directory |
| `make message-assets` | Export shared source messages for the Shell extension without importing GTK |

PO sources and the POT template are reviewed source artifacts; generated MO
files are build artifacts. Template changes accompany marked message changes.
Fuzzy and empty entries use source fallback rather than shipping draft text.
Compilation validates a temporary file before replacing an existing catalogue.

Package staging compiles to
`/usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/locale/<locale>/LC_MESSAGES/oh-no-parent-control.mo`.
Python resolves the directory relative to its module, including relocated
prefixes. The extension's package assets include the same compiled catalogues
under its own `locale/` directory for selected-language lookup. Its archive and
development installation use the same domain and source catalogues as the
distribution packages.

New GTK processes load updated assets. The Shell extension payload follows
session-renewal activation; live translation objects are not hot-reloaded during
package replacement. Packaging changes follow
[package update activation](../Publishing.md#package-update-activation) and the
[installed layout](Lifecycle.md#installed-layout). Catalogue and presentation
changes alone do not require a preference-schema migration.

## Validation contract

Validation separates backend integrity, catalogue behavior, GUI behavior and
installed customer results. It uses the lowest effective scope under
[test maintenance](../../tests/README.md#all-established-regressions), with public
UI actions and observations for customer acceptance.

| Area | Required evidence |
| --- | --- |
| Language backend | Caller-scoped authorization, invalid input rejection, restart persistence, personal-only records, migration, stale-policy and rollback preservation, concurrent writes, corrupt/future record rejection |
| Catalogue infrastructure | Real compiled catalogues; resolution, Unicode, named formatting, contexts, language-specific plurals, missing-entry fallback, corrupt-catalogue errors and Python/GJS parity |
| GUI settings | First-run default, Continue persistence before closure, Preferences reopening, save failure/retry, owning-account isolation and stable public IDs |
| Language application | Visible and accessible text changes, dynamic result text, preserved selections/drafts/focus, child panel refresh and no change to policy or countdown behavior |
| Layout and packaging | Long text and script coverage at supported scales; private staged MO assets in both package formats and the extension archive; translated installed surfaces |

The [localization tests](../../tests/unit/test_localization.py),
[preference tests](../../tests/unit/test_preferences.py),
[broker tests](../../tests/unit/test_core.py) and
[service-contract tests](../../tests/unit/test_service_contract.py) are the
engineering entry points. Host catalogue tests do not establish installed GUI
acceptance. Installed checks select different account languages, exercise Parent,
child overlay, panel and kiosk through public controls, reopen the surfaces and
observe translated results while preserving independent account choices.
