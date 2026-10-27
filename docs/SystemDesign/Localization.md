# Localization

[System design overview](../System-Design.md)

Localization spans Parent, child panel, request overlay and dedicated kiosk.
The [specification](../Specification.md) owns customer behavior,
[State](State.md) owns persistence, and
[Front ends](Frontends.md#personal-language-selection) owns chooser surfaces.

Implementation: [Python context](../../common/oh_no_parent_control_ui/localization.py),
[source messages](../../common/oh_no_parent_control_ui/messages.py),
[deferred messages](../../common/oh_no_parent_control_ui/message.py),
[GTK bindings](../../common/oh_no_parent_control_ui/translation_widgets.py),
[Shell context](../../child/localization.js),
[Shell resolver](../../child/languages.mjs),
[MO decoder](../../child/gettext.mjs),
[language catalogue](../../common/oh_no_parent_control_ui/languages.json).

## Responsibilities and language ownership

| Surface | Language owner |
| --- | --- |
| Parent and its dialogs | Signed-in administrator, independent of selected child |
| Child panel and overlay | Signed-in child |
| Dedicated kiosk and its dialogs | Selected child, independent of approver |
| Product PolicyKit message | Requesting child or selected kiosk child |
| Native authentication controls | System authentication agent |

The broker stores validated language intent and translates only the product-owned
PolicyKit message using the target child's private GTK-independent context.
Empty kiosk language uses the child's desktop language; empty overlay language
defaults to English for that broker message. Frontends resolve their own contexts.
Unsupported selections and missing entries fall back to English.

Normal translation is offline using trusted package assets. No downloaded or
user-supplied catalogue participates. Language never changes policy, grants,
accounts, diagnostics, protocol values or operating-system locale.

## Localization infrastructure

### Language catalogue and resolution

The shared JSON owns ordered IDs, native names, English search names and optional
direction metadata. Python and Shell consume the same asset and preserve its
order. The 62 choices begin with English, German, Spanish, French, Brazilian
Portuguese, Simplified Chinese, Russian, Italian, Polish and Japanese. The
catalogue, rather than a duplicated table, owns remaining choices. Arabic,
Persian, Hebrew, Uyghur and Urdu carry RTL direction.

Saved nonempty values resolve first. Otherwise GTK uses the primary session
message language; kiosk uses the selected child's AccountsService language,
falling back to its session when absent. Unsupported primary/saved values resolve
to English without rewriting saved intent or trying later session languages.
No supplied session language also defaults to English.

Exact IDs resolve case-insensitively, then regions collapse by base language,
with these exceptions shared by Python and Shell:

- Portuguese defaults to `pt`; `pt-BR` selects Brazilian Portuguese.
- Chinese explicit Hans/Hant overrides region. TW/HK/MO select Hant without
  a script; bare Chinese and other regions select Hans.
- Serbian defaults to Cyrillic `sr`; Latn, POSIX `@latin` and legacy `sh`
  select `sr-Latn`.
- `no` maps to Bokmål `nb`; `nn` remains distinct. Legacy `iw`/`in`
  map to Hebrew/Indonesian.

Session locales may include underscores, encodings and modifiers; saved IDs
retain the broker's hyphenated syntax. Product IDs use hyphens and gettext
directories underscores. Only resolved catalogue IDs become path components.
Translation availability is separate from preference validity; missing entries
use source text.

### Translation context

The domain is `oh-no-parent-control`. Each frontend owns a private object with
`gettext`, `ngettext`, `pgettext` and `npgettext`, passed to shared UI.
Messages and named operands remain deferred until the destination renders them.
No global builtins translation, process-wide `setlocale`, or mutation of
`LANGUAGE`, `LANG`, `LC_MESSAGES` or `LC_ALL` applies personal selections.

Python uses standard GNU gettext. Missing entries/catalogues use English,
including plural fallback; malformed/unreadable catalogues are package errors.
Shell explicitly loads the same MO domain without changing Shell/other extensions.
Its decoder validates header, endianness, bounds and UTF-8, and evaluates plural
rules with a bounded integer-expression parser rather than JavaScript eval.
Both implementations share lookup/fallback parity fixtures.

### Message authoring

English source messages live in the shared messages module; Shell receives a
generated asset from that source. Extraction recognizes marked gettext, plural
and context calls. Use complete literal sentences, named placeholders and
post-translation interpolation. Do not concatenate sentence fragments, extract
f-strings, translate user content or implement English-only plural branches.
Translator comments explain operands, meaning and layout. Branding remains
exactly `Oh No! Parent Control`.

Translate before destination-specific HTML/Pango escaping; translation is not
escaping. Catalogue checks preserve operands and format helpers reject invalid
substitutions.

GTK bindings retain source/operands, follow native object lifetime and move with
reparented controls. Shared dialogs inherit their owner's private context.
Relabel existing controls and update visible/accessibility text together.
Apply direction and Pango language only to owned trees, retaining other text
attributes. Native language names retain their own language/direction.
Rich-editor relabeling preserves content, automatic user-text direction and undo.

## Language user settings backend

`personal.language` uses the root-private version-4 UID record, shared locked
atomic writer and migration chain described in [State](State.md).
There is no per-frontend language file.

Own-language methods derive the caller UID and accept administrators/root,
eligible children and configured kiosk. Kiosk-only child-language/context methods
validate an eligible selected child. Parent management permission never permits
editing another account's personal language.

Empty means frontend/session fallback. Explicit IDs contain 2–8 ASCII letters
then optional hyphen-separated 1–8 alphanumeric subtags, at most 63 characters.
Storage preserves valid syntax independently of catalogue support; POSIX locales,
paths and colon-separated lists are rejected.

Writes preserve policy/request choices, and stale policy saves/rollback preserve
latest personal settings. Personal changes do not invalidate approval snapshots.
Personal-only records claim no enforcement ownership. Success follows atomic
mode-0600 replacement and file/directory flush in a mode-0700 directory.
Invalid, duplicate-key or future-schema records refuse replacement.
Migration adds empty language without changing choices. Remove retains records;
purge deletes them. See [migration](Data-Migration.md).

## Language user settings GUI

The [frontend contract](Frontends.md#personal-language-selection) owns concrete
surfaces and IDs. Empty preferences open initial setup; nonempty values bypass
it. Kiosk resolves each child's saved/desktop language before revealing content.
Read failure is an error with retry, never an invented empty selection.

Choosers show native names in catalogue order, searchable by names/IDs with
case-insensitive partial/wildcard matching. Filtering preserves the candidate.
Escape clears search rather than closing. Lists scroll within monitor/gateway
bounds while heading/Save/Cancel remain reachable. Cancel stays physically left
of Save across direction previews.

Candidate selection privately relabels the chooser without rebuilding it or
changing the owner's context. Save persists the explicit ID before closing and
applying it; pending save disables duplicate actions. Failure retains the draft
for retry. Cancel is always available, discards the candidate and leaves unset
preferences to prompt again. Preferences reopens current settings without writing
a default. Empty is a setup state rather than a selectable persistent choice.
Language setup neither authenticates nor submits a request.

## Translation lifecycle and shared UI

Startup establishes the context before main translated content; early notices
use session language/English fallback. After save, relabel existing owned UI and
open shared dialogs. A failed catalogue load retains the last usable context
and reports the error while leaving saved intent authoritative.

Preserve selections, drafts, focus, scroll, policy-save order, request state and
feedback undo. Do not recreate workers/timers/authentication. Async results carry
data or stable categories so they render in the current language.

There is no broker change signal. GTK refreshes on Preferences/process start;
the child panel refreshes on enable, resume and overlay exit without delaying
countdown or locks. Isolated previews share disposable language state, never
product records.

Shared dialogs inherit their owner. User reports/names/paths stay data.
Portal page links (Help, Website and Privacy) use that owner's resolved language:
English keeps the unprefixed URL; other languages prefix the path with the
canonical catalogue ID, such as `/pt-BR/` or `/zh-Hant/`. Open dialog links
refresh with language changes. Page paths retain trailing slashes, including
the overview and Help. Feedback API endpoints remain language-neutral.
Parent's app catalogue selects desktop-entry translations using the parent's
language. GDM/system-owned UI is not relabeled. The broker supplies a complete
translated approval message through supported `polkit.message`, including
plural durations, rest-of-day and soft-app access; the account label remains a
separate validated detail for PolicyKit's single-pass expansion.

The kiosk prepares only its native agent's process environment in a private
runtime file. `LANG` selects registration locale, `LANGUAGE` selects system
catalogues and an installed non-C UTF-8 `LC_ALL` permits gettext when available. It generates
no locales or user-manager/system environment changes. Preparation uses public
systemd restart/job completion, serializes locale changes, reuses identical
successful settings and invalidates old cache on an attempted change.
Failed preparation or its 30-second deadline stops submission; disposal makes
late jobs/replies inert. Job success is not PolicyKit registration proof; the
broker separately bounds an unfulfilled kiosk challenge to five seconds.
Overlay uses its desktop agent, and language changes never recreate an active
password prompt.

### Native authentication fallback

When locale discovery fails or finds no non-C UTF-8 message locale, kiosk
preparation uses an installed C UTF-8 locale, or C, for registration and message
categories, with source text for the vendor agent. This does not change the
child's saved language. A failed discovery uses C without caching the failure;
the next preparation retries the bounded inventory command. Required agent
service preparation and its deadline still apply.

The required behavior is genuine selected-parent authentication with safe
native/source text when locale discovery or translation assets are unavailable.
Optional catalogue presence must not become admission authority. Preserve saved
language and system settings, the vendor privileged helper, public Polkit
protocol and request association; never synthesize a password dialog.
A failed required service job or stale identity still fails safely with retry/exit.
Only genuine authentication establishes operational approval. Machine preparation
remains bounded; human reading/password entry follows the
[lifecycle boundary](Lifecycle.md#machine-work-and-human-pauses).

## Formatting, layout and accessibility

Language does not change time zones, midnight, arithmetic, usage or numeric
transport/input syntax. Durations use localized units/plurals; fractional hours
have dedicated messages where integer rules differ. Attachment-size translation
preserves byte thresholds/numeric scale. Error-report text is translated once
when seeding the editable draft; later relabeling preserves it.

Wrap labels and scroll at supported scales. Use logical alignment/direction,
script-capable fallback fonts and complete combining clusters. Complex-script
GTK contexts select sans-serif/zero letter spacing privately; chooser native
names always support mixed scripts. Shell owned labels apply private Pango
language/direction and reapply after restyling without changing shared contexts.
Keep IDs/actions stable and translate accessible text with visible text.
Images/branding remain language-neutral. RTL additions require layout review.

## Catalogue workflow and packaging

The [Makefile](../../Makefile) owns marked-message extraction, PO validation,
MO compilation and shared Shell message generation. GNU gettext is a DEB/RPM
build dependency. PO/POT files are reviewed sources; MO files are generated.
Validate headers, language-specific plural rules and placeholders; fuzzy/empty
entries fall back to source. Validate temporary output before replacement.

Python loads module-relative
`locale/<locale>/LC_MESSAGES/oh-no-parent-control.mo`; Shell packages the same
catalogues under its payload. New GTK processes load assets; child payload uses
session renewal. Catalogue/presentation changes alone require no preference
migration. See [installed layout](Lifecycle.md#installed-layout).

### What's New translation workflow

English Parent Markdown is authored in [VersionHistory](../VersionHistory.md);
optional child notes are in [child TOML](../../data/whats-new-child.toml).
Recurring translation uses the established `tools/sync-whatsnew` interface.

**Synchronization requires an explicit user request.** Editing notes, building
or publishing never authorizes automatic synchronization, including `--prepare`.
Read-only `--check` and `make check-whats-new-translations` remain allowed;
report pending work rather than starting translation automatically.

Scope is only the highest numeric Parent release and a matching child record,
if present. Record order, installed version and future/older child records do
not select scope. Normalize trailing version zeros. Preserve English,
infrastructure, application catalogues and all older translations.

Sources live in `po/whats-new/<canonical-version>/`, with one POT and PO per
non-English language. Each complete Markdown record is a singular message
contextualized by `whats-new:<record_id>`. Separate versioned domains reuse
application locale metadata/terminology. Unchanged records retain translations;
changed English preserves previous text and marks translation fuzzy until
reviewed. Repeated preparation retains that state. Record-content edits do not
change [acknowledgement identity](State.md#whats-new-backend).

Translation workers return text; only the maintained synchronization operation
writes translation assets. Validate exact language/record assignment, nonempty
content, Markdown structure, URLs, code, placeholders, versions and branding,
with semantic review of policy meaning, omissions and region/script.
Concurrent source/catalogue changes refuse application while preserving newer
work. Failed runs retain validated batches and resume pending entries.
There is no commit/publication authority in translation synchronization.

Release checks require current-source nonempty/non-fuzzy translations and GNU
gettext validity. Build/staging compiles existing catalogues, including older
domains, without translating them. The GTK-independent adapter translates
broker English before rendering in the owner's resolved language. Missing,
fuzzy or mismatched entries fall back to English.

## Validation contract

Validation distinguishes backend integrity, catalogue parity, GUI behavior and
installed results. Cover caller isolation, invalid/corrupt/future data rejection,
durability, migration, concurrency and stale-policy preservation; complete plural/
context/Unicode/operand parity across Python/Shell; Save-before-close, Cancel,
retry and independent account choices; preserved drafts and enforcement;
long/RTL/complex-script layouts and packaged catalogues in both formats.

Host checks do not establish installed GUI acceptance. Installed checks use
public controls to reopen translated Parent, overlay, panel and kiosk while
preserving independent language selections.
