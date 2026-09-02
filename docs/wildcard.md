# Update-stable native application patterns

## Status

Wildcard application policy is implemented as a broker-owned compiler in the
preference schema, D-Bus catalog, parent UI, and execution-policy renderer.

Do not require fapolicyd 2.x on the supported Ubuntu 26.04 baseline. Ubuntu
ships fapolicyd 1.3.6 there. Upstream fapolicyd 2.x is not provided as a
supported Ubuntu 26.04 package, and packages from a later Ubuntu series must not
be mixed into the baseline. The package dependency must remain `fapolicyd`
without a 2.x minimum.

The current root-cause mitigation remains useful: immediately before saving an
application policy, the broker resolves each selected desktop ID from the
child's current launcher and replaces the parent window's cached concrete
target. This handles an update which occurred while the parent window was open,
but it does not protect against a later update without another policy save.

## Recommended architecture

Implement patterns as a broker-owned policy compiler on top of Ubuntu's
fapolicyd 1.3.6 primitives. Do not write a second fanotify execution daemon.

The enforcement layers have separate jobs:

- Malcontent receives concrete current targets and continues to provide its
  supported GNOME launcher and Flatpak integration.
- Existing UID-scoped fapolicyd rules deny concrete native targets, covering
  direct execution paths which bypass the launcher UI.
- The pattern compiler converts a same-directory filename pattern into ordered
  exact allow rules followed by a fail-closed fapolicyd `dir=` denial.

Pattern denial must not depend on Malcontent at execution time. It complements
Malcontent, while remaining derived from the same broker-owned application
policy and effective hard/conditional state.

Do not implement patterns by watching a directory and adding an exact deny only
after a matching file appears. An updater could execute the new file before the
watcher reloads fapolicyd. A watcher may improve availability, but it must not
be the security boundary.

## Fail-closed compilation

For child UID 1001 and pattern:

```text
/home/adrian/Applications/*Lunar*Client*.AppImage
```

compile one guarded directory. Rules are ordered as follows:

1. Deny every concrete blocked native target. This includes blocked
   nonmatching applications which happen to share the guarded directory.
2. Allow each currently executable direct child of the directory whose basename
   does not match any active pattern for that directory.
3. Allow each representable existing immediate subdirectory, because a
   basename-only pattern does not cross a slash.
4. Deny execution for the child UID from the entire directory prefix.

Conceptually:

```text
deny_syslog perm=execute uid=1001 : sha256hash=<current-lunar-hash>
allow perm=execute uid=1001 : path=/home/adrian/Applications/PrismLauncher.AppImage
allow perm=execute uid=1001 : dir=/home/adrian/Applications/tools/
deny_syslog perm=execute uid=1001 : dir=/home/adrian/Applications/
```

fapolicyd evaluates the first complete matching rule. The final directory rule
therefore denies a future Lunar version before the broker sees its filesystem
event. A newly created nonmatching executable is also denied initially; after
classification, the broker may safely add an exact allow rule. Missing or
dropped watcher events cause overblocking rather than a pattern bypass.

Compile all effective patterns for the same UID and directory together. A file
gets an allow exception only when its basename matches none of those patterns
and it is not a concrete blocked target. Emit at most one final directory denial
per UID and directory.

## fapolicyd 1.3.6 representation limits

Version 1.3.6 splits rule values on whitespace and commas and has no quoted path
syntax. Its SHA-256 object attribute is suitable for denying an otherwise
unrepresentable concrete executable, but it is not a safe substitute for an
exact allow exception inside a guarded directory. A nonmatching file could be
renamed to a matching basename without changing its hash and retain the earlier
hash allowance.

Consequently:

- The guarded directory itself must be representable as a literal 1.3.6 rule
  token. Reject whitespace, commas, quotes, backslashes, control characters,
  and other parser-significant characters conservatively.
- Exact nonmatching allow paths and allowed subdirectory prefixes must also be
  representable. Never generate a hash-based allow exception.
- If an existing nonmatching executable or relevant subdirectory cannot be
  represented, do not silently broaden the policy. Either reject pattern
  activation or keep that entry denied and show a persistent collateral-block
  warning. Rejecting activation is the simpler initial contract.
- A matching filename may contain spaces because it receives no allow rule; the
  representable parent directory's final `dir=` denial catches it.
- Continue using the current stable hashing implementation for concrete blocked
  paths containing whitespace, independently of the pattern compiler.

The rule generator must remain constrained rather than attempting to escape
unsupported syntax. Generate product-owned component rules, replace them
atomically, call the packaged `fagenrules --load`, verify the result where the
packaged public interface permits it, and restore/reload the previous component
file on failure.

## Pattern contract and validation

Patterns are native-path policies only. Flatpak references stay exact and are
handled through Malcontent/Flatpak.

Use the following initial contract:

- Store an absolute directory plus one basename component.
- Permit `*` and `?`; do not initially support bracket expressions or recursive
  `**` syntax.
- Match case-sensitively against the complete basename.
- Wildcards never cross `/` because only a basename is matched.
- Require at least one wildcard.
- Reject slash, NUL, CR, LF, comma, quote, and backslash in the basename.
- Restrict the pattern to the same resolved directory as an owning concrete
  native target.
- Resolve launcher targets with the same `realpath` behavior used by the
  application catalog. Document that hard links, bind-mount aliases, copied
  binaries, and alternate paths are outside this filename-pattern identity.

Use one shared matcher implementation for catalog suggestions, parent preview,
filesystem classification, preference validation tests, and policy compilation
tests. Do not hardcode Lunar Client or any application name.

## Version detection and parent UI

When a native executable basename contains a version-like numeric component,
the catalog may suggest replacing that component and updater suffix with `*`
while retaining an alphabetic executable suffix such as `.AppImage`.

Example:

```text
Lunar Client-3.7.17-ow_2eff89.AppImage
Lunar Client-*.AppImage
```

The parent must:

- warn that a future update is likely to use another filename;
- present the suggestion as editable text rather than enabling it invisibly;
- allow a parent to enter a broader value such as
  `*Lunar*Client*.AppImage`;
- mark the application row with a distinct pattern indicator;
- allow clearing the pattern to retain exact-target policy only; and
- disable saving when the guarded directory cannot be represented safely by
  fapolicyd 1.3.6.

The live preview must show every filesystem execution target that the matcher
currently selects, not only catalogued `.desktop` applications. Map catalogued
targets to application names, and label other executable files as unregistered
paths. This lets the parent detect a pattern which is too wide or too narrow.
Show zero matches as a warning, but permit it if the parent explicitly confirms
that the pattern is intended for a future version.

## Reconciliation and conditional policy

Saved patterns are canonical preferences. Generated fapolicyd rules and the
Malcontent AppFilter are derived enforcement state.

- A permanent pattern is always active.
- A conditional pattern is active exactly when its owning concrete application
  is present in the effective live blocklist.
- Temporarily allowing soft-blocked applications removes both their concrete
  deny and their pattern contribution. If another active pattern guards the
  same directory, recompile the combined directory policy rather than removing
  its guard.
- Parent saves must apply the concrete AppFilter and compiled fapolicyd policy
  transactionally with read-back and rollback.
- The existing AccountsService `PropertiesChanged` reconciliation path must
  recompute effective pattern state after an approved child request changes the
  AppFilter.

Monitor active guarded directories for create, move, delete, replacement, and
mode-change events. Reconcile through a bounded, coalescing worker so an updater
cannot cause unlimited reloads. Also rescan periodically and at broker startup.
The final directory denial remains active while rescanning or after a monitor
failure. Report degraded availability when safe nonmatches cannot be admitted;
never remove the guard merely to recover convenience.

## Data and interface changes

When implemented under the current unpublished-product assumption, preferences
may move directly to:

```text
apps[desktop-id] = { state, targets[], patterns[] }
```

No migration is needed only while there are no published installations. If that
assumption changes, follow `docs/Data-Migration.md` before changing readers or
writers. Extend `ListApplications` with suggested patterns only when the parent
and broker changes land together.

The likely implementation areas are:

- `broker/oh_no_parent_control/catalog.py`: version detection and suggestions;
- `broker/oh_no_parent_control/preferences.py`: canonical pattern validation;
- `broker/oh_no_parent_control/execution_policy.py`: directory-guard compiler;
- `broker/oh_no_parent_control/adapters.py` and `core.py`: effective-state
  projection, transactions, and rollback;
- `broker/oh_no_parent_control/service.py` and the D-Bus XML: catalog transport;
- `parent/oh_no_parent_control_parent/`: editor, indicator, validation, and full
  filesystem match preview; and
- the broker service sandbox/activation manifest only if new filesystem monitor
  access or installed integration files are required.

Any added system integration must be classified using `docs/Package-Update.md`.
Broker code, generated fapolicyd component rules, and broker-owned directory
monitor behavior are expected to remain `process-restart` activation unless the
implementation adds a login, PAM, GDM, or session-boundary component.

## Required verification

Unit tests must cover pattern validation, version suggestions, same-directory
restriction, combined patterns, unsafe 1.3.6 paths, exact-deny precedence,
subdirectory allowances, no hash-based allows, conditional relaxation, rollback,
monitor coalescing, and the parent's complete match preview.

A disposable Ubuntu 26.04 VM with the archive fapolicyd 1.3.6 package must prove:

1. the current Lunar executable is denied from GNOME, Files, a trusted desktop
   file, and a shell;
2. a new matching version created and executed before broker reconciliation is
   denied by the existing directory guard;
3. an existing safe nonmatch in the same directory remains executable;
4. a new safe nonmatch is initially denied and becomes executable only after a
   verified reconciliation;
5. an unrepresentable nonmatch cannot create a hash-allow rename bypass;
6. hard and conditional patterns follow their effective state correctly;
7. broker or monitor failure leaves the guard active;
8. restart reconstructs the same policy from canonical preferences; and
9. Flatpak behavior remains governed by the concrete Malcontent filter.

Do not advertise wildcard enforcement until this VM matrix passes. The Ubuntu
1.3.6 manual confirms exact `path`, prefix `dir`, SHA-256, UID subjects, and
first-match ordering; it also confirms that globbing is unavailable. Those are
the only rule-language properties this design assumes.
