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
[Shell locale resolver](../../child/languages.mjs),
[MO decoder](../../child/gettext.mjs),
[languages.py](../../common/oh_no_parent_control_ui/languages.py),
[language catalogue](../../common/oh_no_parent_control_ui/languages.json),
[preferences.py](../../broker/oh_no_parent_control/preferences.py),
[broker core](../../broker/oh_no_parent_control/core.py),
[D-Bus service](../../broker/oh_no_parent_control/service.py),
[Parent chooser](../../parent/oh_no_parent_control_parent/language_dialog.py),
[request chooser](../../kiosk/oh_no_parent_control_kiosk/preference_dialog.py),
and [Makefile](../../Makefile).

## Responsibilities and language ownership

Language is a personal presentation preference belonging to the operating-system
account running the surface, except the dedicated kiosk, which follows its
selected child. It does not follow the child selected in Parent or the approver
selected in a request form.

| Surface | Language owner | Selection UI |
| --- | --- | --- |
| Parent App | Signed-in administrator | Parent Preferences |
| Child Shell panel | Signed-in child | Preferences in the child request overlay |
| Child request overlay | Same child as the panel | Request Preferences |
| Dedicated kiosk | Selected child | Request Preferences |
| Shared About, feedback and error windows | Owning frontend account | Inherit the frontend translation context |
| Product-owned PolicyKit approval message | Signed-in child, or selected child in kiosk | Same saved child preference as the request form |

The broker authenticates the caller and stores language intent. Frontends resolve
that intent against the language catalogue, load message catalogues and render
text. For the product-owned PolicyKit approval message, the broker loads the same
GTK-independent private translation context using the validated target child's
saved language. It supplies no root-session language: an empty kiosk selection
uses the child's AccountsService desktop language, while an empty overlay
selection defaults to English. Unsupported selections and missing entries
retain English source fallback. It never translates policy, protocol values or
diagnostics.

All normal localization works offline. Catalogues are trusted package assets,
with no runtime download, remote translation service or user-supplied catalogue.
Changing language changes presentation; it does not modify grants, limits,
application policy, accounts or operating-system language settings.

## Localization infrastructure

### Language catalogue and resolution

The shared JSON catalogue owns ordered product language IDs, native display
names and English names for chooser search. Python reads it without GTK; the same JSON is packaged with the
Shell extension. Native names remain recognizable regardless of the active UI
language and are not translated into that language.

The catalogue is a hardcoded ordered list of 62 choices. Its first ten are the
requested priority order: English, German, Spanish, French, Brazilian Portuguese,
Simplified Chinese, Russian, Italian, Polish and Japanese. Remaining choices
follow the published sequence in the
[W3Techs content-language survey](https://w3techs.com/technologies/overview/content_language),
with additional Portuguese, Chinese and Serbian variants beside the corresponding
language's remaining position. Website content is an indirect prioritization
proxy, not a measurement of Ubuntu/Linux users' language market share. Neither
the requested percentage estimates nor inferred Linux percentages are stored.
Consumers preserve JSON order; they do not sort names or fetch rankings at runtime.

Coverage was selected on 2026-10-01 using the official
[GNOME language list](https://l10n.gnome.org/languages/) and
[GNOME 50 UI statistics](https://l10n.gnome.org/releases/gnome-50/), the project's
desktop baseline. It includes the languages with at least 80% UI translation
coverage in that reference, consolidating English regional variants and Chinese
regional variants into the product's script choices. Arabic, Bengali, Croatian,
Estonian, Icelandic, Malayalam, Marathi, Malay, Punjabi, Tamil, Telugu, Urdu and
Vietnamese add regional coverage below that threshold. GNOME completion measures
translation coverage, not user population.

Translation delivery completed on 2026-10-02 against the current 359-message POT.
All 61 non-English catalogues contain every message, including contextual and
language-specific plural forms, with no empty or fuzzy entries. This includes
all 52 former scaffolds. English intentionally uses the source messages. The
62-choice catalogue order, native names, branding, operands and markup are
preserved. Authors reread their complete catalogues; separate reviewers checked
critical policy/privacy meanings, plural and fractional forms, and the literal
translations used as GUI expectations.
The PO headers cite GNOME team plural metadata; Uzbek uses the invariant
single-form convention where the reference leaves its rule unspecified.
Arabic, Persian, Hebrew, Uyghur and Urdu have `direction: "rtl"` metadata for
their translated surfaces and native-name labels. Other entries default to
`ltr`. These five RTL languages were reviewed across Parent, the request overlay,
kiosk, feedback and the child panel. Long-text and complex-script checks cover
the same frontend surfaces, including font fallback, combining clusters and
switching back to English.

Delivery validation passed full-message Python/Node/GJS parity for every
non-English catalogue, scoped maintained unit and GTK/nested-Shell UI checks,
gettext validation and the final `make build` for both DEB and RPM. The checks
preserve selections, unsaved input, feedback drafts and undo state. This is
checkout engineering validation; installed customer acceptance remains governed
by the validation contract below. Nothing was installed on the development host
or published.

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
| `pt` | Português | `pt` |
| `nl` | Nederlands | `nl` |
| `tr` | Türkçe | `tr` |
| `zh-Hant` | 中文（繁體） | `zh_Hant` |
| `id` | Bahasa Indonesia | `id` |
| `fa` | فارسی | `fa` |
| `cs` | Čeština | `cs` |
| `vi` | Tiếng Việt | `vi` |
| `ko` | 한국어 | `ko` |
| `uk` | Українська | `uk` |
| `ar` | العربية | `ar` |
| `hu` | Magyar | `hu` |
| `sv` | Svenska | `sv` |
| `ro` | Română | `ro` |
| `el` | Ελληνικά | `el` |
| `da` | Dansk | `da` |
| `fi` | Suomi | `fi` |
| `he` | עברית | `he` |
| `sk` | Slovenčina | `sk` |
| `th` | ไทย | `th` |
| `bg` | Български | `bg` |
| `hr` | Hrvatski | `hr` |
| `sr` | Српски | `sr` |
| `sr-Latn` | Srpski (latinica) | `sr_Latn` |
| `nb` | Norsk bokmål | `nb` |
| `lt` | Lietuvių | `lt` |
| `sl` | Slovenščina | `sl` |
| `ca` | Català | `ca` |
| `et` | Eesti | `et` |
| `lv` | Latviešu | `lv` |
| `bn` | বাংলা | `bn` |
| `hi` | हिन्दी | `hi` |
| `ka` | ქართული | `ka` |
| `is` | Íslenska | `is` |
| `ms` | Bahasa Melayu | `ms` |
| `uz` | Oʻzbekcha | `uz` |
| `kk` | Қазақша | `kk` |
| `eu` | Euskara | `eu` |
| `gl` | Galego | `gl` |
| `ur` | اردو | `ur` |
| `mr` | मराठी | `mr` |
| `nn` | Norsk nynorsk | `nn` |
| `ta` | தமிழ் | `ta` |
| `ne` | नेपाली | `ne` |
| `be` | Беларуская | `be` |
| `te` | తెలుగు | `te` |
| `ml` | മലയാളം | `ml` |
| `pa` | ਪੰਜਾਬੀ | `pa` |
| `eo` | Esperanto | `eo` |
| `ug` | ئۇيغۇرچە | `ug` |
| `oc` | Occitan | `oc` |
| `fur` | Furlan | `fur` |

Resolution uses the saved language when nonempty. An empty value uses the primary
frontend session message language, supplied by `GLib.get_language_names()` for
GTK. Dedicated kiosk instead supplies the selected child's AccountsService
`Language`; an absent desktop language falls back to the kiosk session.
An unsupported primary language resolves to English, rather than searching
later session-language entries. A nonempty unsupported saved ID also resolves to
English and remains preserved in storage. With no frontend session language
supplied, resolution defaults to English.

Exact catalogue IDs resolve first, case-insensitively. Remaining regional variants
collapse by base language except for these explicit choices, implemented with
matching Python and Shell resolvers:

- Portuguese uses `pt` by default, including `pt-PT`; `pt-BR` selects Brazilian Portuguese.
- Chinese uses an explicit `Hans` or `Hant` script before region. Taiwan, Hong Kong
  and Macao select `zh-Hant` when no script is supplied; other regions and bare
  `zh` select `zh-Hans`.
- Serbian uses Cyrillic `sr` by default; `sr-Latn`, POSIX `@latin`, and the legacy
  `sh` alias select `sr-Latn`.
- Norwegian `no` maps to Bokmål `nb`; Nynorsk `nn` stays separate. Legacy `iw`
  maps to Hebrew `he`, and `in` maps to Indonesian `id`.

POSIX session locales may contain underscores, encoding suffixes and modifiers;
saved preference syntax remains the broker's hyphenated-ID contract. Existing
saved `pt-BR` and `zh-Hans` selections retain their identity. For example, `fr-CA`
still resolves to `fr`. Adding further distinct variants requires updating both
resolvers and their parity checks together.

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
parent's context. Direction changes apply to the owning GTK trees, including
shared dialogs and newly adopted controls, without changing GTK's global
direction. GTK mirrors logical label alignment itself. Native labels and entry
text carry the private context's Pango language so font fallback can shape
complete script clusters even when the session has no message language. Existing
text attributes are retained. Native-name labels retain their own catalogue language and
direction, independently of the chooser's candidate.
Rich editor labels and document language/direction are updated in the existing
document; editable user content keeps automatic text direction, its content and
undo state. Product branding remains exactly `Oh No! Parent Control` in every
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
| `GetChildLanguage` | Child UID | Saved language string | Configured kiosk caller; eligible child target |
| `GetChildLanguageContext` | Child UID | Saved language and AccountsService desktop language | Configured kiosk caller; eligible child target |
| `SetChildLanguage` | Child UID, language string | Persisted language string | Configured kiosk caller; eligible child target |

The own-language methods accept no target UID. Administrators, including root, eligible
children and the configured kiosk account may access their own language.
Authorization occurs before storage access; syntax validation occurs before a
write. Parent's policy-editing authority does not grant a method for changing
another account's personal language. See [broker permissions](Broker.md#broker-interface-and-roles).
The kiosk's child-language methods share the child's personal record with the
overlay and panel; they grant no policy, authentication or operating-system changes.

Empty means follow the frontend session language, or the selected child's
desktop language in kiosk. Explicit IDs contain 2–8 ASCII
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

Parent and child overlay read their own language asynchronously at startup.
Kiosk reads the selected child's saved and desktop language through
`GetChildLanguageContext` at startup and each child selection.
A nonempty saved value bypasses the chooser. An empty value opens a modal chooser
with the resolved primary session language selected, or the child's desktop
language in kiosk. Kiosk keeps its content hidden until this initial read
finishes, then applies that language to the form and chooser together.
The chooser displays native
language names in catalogue order, using the same heading for initial setup and
subsequent visits.

Both choosers filter as the user types in the search box. Search matches any part
of a native language name or product language ID, ignoring case and allowing
`*` and `?` wildcards. Clearing the search restores catalogue order; filtering
preserves the candidate selection. The viewport aims to show the first ten
languages without scrolling, with remaining choices available by scrolling.
Escape clears the search from anywhere in the dialog without dismissing it or
changing the candidate selection. Search publishes a translated accessible name
and description, native editable text semantics and a stable `language-search`
ID. Filtered-out choices leave the accessible tree and keyboard navigation;
the list, visible language choices and actions retain native keyboard focus.
Parent caps the dialog to its hosting monitor; the request chooser caps it to
the gateway's inner rails. Smaller contexts show fewer rows and retain scrolling.

Both chooser lists scroll, keeping the heading and Save/Cancel actions outside
the scrolling list. Native-name text direction follows catalogue metadata.
The action row keeps Cancel on the left and Save on the right when previewing
any language, so switching direction cannot move Cancel into Save's position.
The button text follows the candidate language's direction.

Parent uses its native GTK dialog; the kiosk and overlay share their separate
metal-board dialog. Both share catalogue and resolution logic. Save commits the
selected explicit product ID through `SetOwnLanguage` (or kiosk-only
`SetChildLanguage`) before closing. Parent
always offers Cancel, including first-time setup; it continues startup without
writing or applying the candidate, leaving the chooser to appear on the next
launch while the preference remains empty. Kiosk and overlay also always offer
Cancel; kiosk prompts again when that child is next selected while unset.
Cancel never writes the candidate or applies it to the owning frontend.
Saving disables search, the choices, Save and Cancel to
prevent duplicate submissions. A failure retains the choice, displays an error
and enables retry.

The top-right Preferences action reopens the chooser with the account's saved
selection. Opening it does not write a default. Selecting a language immediately
translates the chooser's visible and accessible text in its private context.
Existing controls are relabeled in one main-loop turn without hiding, remapping
or rebuilding the dialog. Native language names remain unchanged. The owning
frontend keeps its active context until Save commits the candidate successfully.

The empty storage value supplies the first-run default; the chooser's Save
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
`language-choice-<lowercase-id>`, `language-continue` (Save) and `language-cancel`
stay stable across
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

The isolated `make preview-child` has no broker. Its Shell and request overlay
share a language file under the preview's disposable state directory, supplied
by `OH_NO_PARENT_CONTROL_PREVIEW_LANGUAGE_FILE`. Save replaces that file before
applying the selection; closing the overlay reloads it into the panel context.
Reopening the overlay retains the selection for that preview's lifetime.

About, help labels, feedback controls, validation, request results and user-facing
error explanations inherit the caller's context. Error categories and diagnostic
payloads stay stable. User-written reports, account names, filenames and external
application names remain data. Parent's shared App Limits/revoke catalogue uses
desktop-entry name and comment translations for the calling parent's saved
language, falling back to the OS entry when absent. The selected child's language
does not select those translations. Product locale does not relabel GDM or other
system-owned UI. The broker also translates
the product-owned PolicyKit approval message through the supported
`polkit.message` detail. Complete prompts cover requested time, rest-of-day and
optional soft-app access; duration units use shared gettext plural rules and a
localized list separator. The account label remains a separate validated detail
for PolicyKit's single-pass property expansion. An unset kiosk preference also
uses the child's desktop language for this message.

The standard MATE authentication agent owns its labels, buttons and errors.
Before a dedicated kiosk request, [agent_locale.py](../../kiosk/oh_no_parent_control_kiosk/agent_locale.py)
atomically writes a private environment file under the kiosk's XDG runtime
directory. Its systemd user unit consumes this through `EnvironmentFile`.
`LANG` supplies the agent's PolicyKit registration locale; `LANGUAGE` selects
native system catalogues (including `zh_CN`/`zh_TW`). The public `locale -a`
inventory supplies an installed non-C UTF-8 locale for `LC_ALL`, preferring the
selected language. When that libc locale is unavailable, `LANGUAGE` still selects
the native catalogue under another installed UTF-8 locale. C locales cannot be
used here because GNU gettext ignores `LANGUAGE` in them. No locales are generated.
These settings apply only to that service's process; the product process,
user manager environment, child desktop and OS settings are unchanged.
The kiosk calls the user manager's public `RestartUnit` method and waits for
the matching successful `JobRemoved` result before requesting approval.
Identical successfully applied settings reuse the agent; failures or the
30-second deadline stop submission and use the ordinary error path.
Attempting a different locale invalidates the prior successful cache, including
when the restart fails or completes after the deadline.
Service startup does not establish PolicyKit registration readiness. The broker
allows up to five seconds for an unfulfilled kiosk challenge after service
startup, as defined in [authorization](Broker.md#authorization-and-grant-transactions).
No custom agent, dialog rewriting or authentication change is involved.
The child overlay continues to use its desktop's agent. A language change
during authentication does not recreate the prompt; request controls keep the
child fixed until that request finishes. External text coverage depends on
installed system translations.

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

For joining and complex scripts, the private GTK context marks its owned roots
for the frontend stylesheets' sans-serif family and zero letter spacing. This
avoids isolated pixel-font letters, follows language changes in both directions,
and leaves process locale and other contexts untouched. The request chooser's
native names always use a script-capable sans-serif family because one list
contains multiple scripts regardless of the candidate language.

The child panel, tooltip and context-menu text likewise carry private Pango
language attributes. Existing styling is retained; Shell's shared text context
and session language remain unchanged. Label-owned handlers reapply the language
after Shell restyling replaces text attributes and disconnect when labels are
destroyed. The extension applies its context's direction to its own actor trees,
including newly opened menus.

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

### What's New translation workflow

Developers author US English Parent Markdown in
[`VersionHistory.md`](../VersionHistory.md) and optional child notes in
[`data/whats-new-child.toml`](../../data/whats-new-child.toml). The established
[`tools/sync-whatsnew`](../../tools/sync-whatsnew) launcher owns recurring
preparation, coding-agent sessions and validation. Future synchronization changes
translation assets only; it does not change the infrastructure.

```sh
tools/sync-whatsnew
tools/sync-whatsnew --check
```

The launcher selects the **highest numeric release version in VersionHistory**,
including its Parent body and any matching child TOML record. Child notes may
have no matching entry or an empty record list. Older and future child entries
do not change the selected release. Record order, installed version and
`data/app.json` do not select its scope. `1.10.0` normalizes to `1.10`.
Older versions are never translated, even if their English changed. Missing or
invalid Parent history is an error. Targets come from `languages.json`; English
uses the US English sources. Both source files are checked for concurrent edits.

Sources live in `po/whats-new/<canonical-version>/`: one `whats-new.pot` and
one `<underscore-locale>.po` per non-English language. Separate release-note
domains reuse gettext, language resolution and existing UI terminology without
modifying application POT/PO files. Each complete Markdown record is one singular
message: context `whats-new:<record_id>`, exact English `Content` as `msgid`.
Existing application headers supply language/plural metadata.

New records create pending entries. Edited English replaces the source message,
preserves previous English/translation for reference, and marks translations
fuzzy until reviewed. Repeated preparation preserves that flag. Unchanged complete
records retain their translations; new audience records are independent. Removing
a latest-release record retires only its latest-version entries. Older version
directories are never rewritten. Content edits preserve the
[acknowledgement identity](State.md#whats-new-backend).

Defaults are **GPT-6.1 Sol High, Standard speed**, eight pending languages per
fresh session, and up to two read-only translator/reviewer subagents. High is
recommended for semantic translation/review; independent language batches suit
bounded delegation. Helpers receive disjoint assignments, return text and may
not delegate further. The coordinator reviews meaning, policy terms, omissions,
natural grammar, region/script and Markdown. `--subagents 0` selects serial work;
`--batch-size`, `--model` and `--effort` override defaults. The selected pair must
exist in the local CLI catalogue; no silent substitution occurs. Only
`gpt-6.1-sol` is accepted for Sol. Existing CLI authentication is required.
The [official noninteractive interface](https://learn.chatgpt.com/docs/non-interactive-mode)
owns the ephemeral transport; [model guidance](https://learn.chatgpt.com/docs/models#gpt-61-sol)
documents model selection.

Coordinator and helpers use **read-only workspace sandboxes**. They return
schema-constrained text; only the launcher writes latest-version PO/POT sources.
Agents may not edit infrastructure, English TOML, UI catalogues, history,
preferences or Git state, or run setup/builds/tests, install or publish. Prompts
authorize only their pending batch and treat release content as data, including
embedded instructions. The launcher performs no commits or publication.

Every response must contain exactly its assigned languages/record IDs. Before
any batch write, validation checks nonempty text, heading/list structure, bold
formatting, URLs, code, placeholders, numeric versions and branding. These
conservative guards supplement semantic review; they are not a quality score or
a complete Markdown parser. Source/language changes and concurrent catalogue
edits refuse application while preserving newer work. Final validation requires
all current-source translations to be nonempty/non-fuzzy and checks GNU msgfmt
syntax/format validity. Failed runs retain validated earlier batches; reruns
translate only pending records.

`--prepare` prepares translation assets without a model; `--check` validates
without writes or a model. A complete normal run needs no further agent session.
Shared detached ownership, rendering, retention and cancellation apply. Reinvoke
to attach; `--stop` cancels only the owned session and awaits cleanup. Ctrl+C
detaches the observer. Operational artifacts use the shared `sync-whatsnew`
storage category.

Before release, run `make check-whats-new-translations`, equivalent to `--check`.
Until the first translation run, it correctly reports pending translations;
infrastructure setup does not claim translation delivery. Development builds
retain English fallback. `make translations` and package staging compile
existing PO sources into
`locale/<locale>/LC_MESSAGES/oh-no-parent-control-whats-new-<version>.mo`.
The package manifest includes PO sources and the maintained compiler. Packaging
may compile older catalogues but does not translate them.

The GTK-independent
[`whats_new.py`](../../common/oh_no_parent_control_ui/whats_new.py) adapter uses the
owning frontend's personal/session language, loads the versioned domain and
translates broker English with `translate_content` before rendering. Missing,
fuzzy or current-source-mismatched translations fall back to English. The
What’s New frontend remains pending under the
[specification](../Specification.md#product-information); this adapter implements
no menu, dialog, rendering or link action.

Future-session prompt:

> Run `tools/sync-whatsnew` to translate new or changed records for the latest
> numeric release in `docs/VersionHistory.md` and any matching record in
> `data/whats-new-child.toml` into all supported languages. Use the
> established infrastructure, preserve unchanged and older translations, and
> report completeness and validation. Change translations only; do not change
> infrastructure or English source.

## Validation contract

Validation separates backend integrity, catalogue behavior, GUI behavior and
installed customer results. It uses the lowest effective scope under
[test maintenance](../../tests/README.md#all-established-regressions), with public
UI actions and observations for customer acceptance.

| Area | Required evidence |
| --- | --- |
| Language backend | Caller-scoped authorization, invalid input rejection, restart persistence, personal-only records, migration, stale-policy and rollback preservation, concurrent writes, corrupt/future record rejection |
| Catalogue infrastructure | Every current POT message in all 61 non-English compiled catalogues; Python/Node/GJS lookup parity, contexts, all plural indexes, Unicode, operands, markup, branding and numeric input guidance; resolution, missing-entry fallback and corrupt-catalogue errors |
| GUI settings | First-run default, Save persistence before closure, Cancel on every surface without candidate persistence, prompting again while unset, kiosk child-language restoration on selection, Preferences reopening, save failure/retry, account isolation and stable public IDs |
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
