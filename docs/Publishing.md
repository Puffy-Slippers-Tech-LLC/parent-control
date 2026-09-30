# Publish an app upgrade

Run all local tests from the development checkout before publishing:

```sh
make test-all-verify
```

Prepare and commit the release inputs on `main`, including the dated release
history entry. Create `releases/vX.Y` from that commit and check it out in a
separate enlistment. For example, for version 1.3 with a linked worktree:

```sh
git branch 'releases/v1.3' 'main'
git worktree add '../parent-control-release-1.3' 'releases/v1.3'
```

An independent clone is also supported: push the prepared release branch, then
clone/check out that branch in the release enlistment. Configure its local
signing credentials as described below. Linked worktrees locate the checkout
holding `main` automatically. For an independent clone, configure the main
development checkout once (otherwise the publisher asks for its path):

```sh
git config --local 'onpc.publishMainCheckout' '/absolute/path/to/main-checkout'
```

From the release checkout, run:

```sh
make publish
```

It takes no parameters and publishes the newest entry in
[`VersionHistory.md`](VersionHistory.md) end to end. It requires a clean
`releases/vX.Y` branch matching that entry. Running it is the release
decision: it creates signed source and tags in the public Git repository and
uploads the signed source package to the configured Launchpad PPA. Editing or
testing the publishing tool does not authorize a live release.

The publisher highlights the main checkout and asks you to confirm that it is
clean and development is paused. Keep main paused until the highlighted
**MAIN UPDATED** message appears. That message means the metadata cherry-pick
and push have completed, and local main is clean and synchronized with
`origin/main`. Resume development immediately; Launchpad monitoring and release
checkout finalization continue independently. No manual fetch, pull,
cherry-pick or push is needed on main after this handoff.

To check or resume monitoring an uploaded release without publishing anything,
run this from its release checkout:

```sh
make publish-status
```

It checks the exact version in the latest local release journal, including a
completed release. Without a journal it selects the newest source version for
resolute in the PPA. It immediately checks publication, prints green success and
exits if verified, or continues polling with the same checks as `make publish`.
A recorded attempt that has not reached the upload step reports an error; this
command cannot upload it. The target invokes `tools/publish.py --status`.

[`tools/publish.py`](../tools/publish.py) is the single publishing entry point.
Its supporting source-verification and signing modules live in
[`tools/publishing/`](../tools/publishing/). The Debian installation helper
[`packaging/package_activation.py`](../packaging/package_activation.py) determines
restart/reboot requirements for installed files; it is not a publishing command.

## Release history and source inputs

Commit application changes and the new history entry on `main` before creating
the release branch. All release inputs must be committed; staged, unstaged and
untracked changes cause an error before signing, building, or publishing. Ignored files,
including `.envrc` and local build output, are not copied into the release clone.

Use this format, with at least two entries:

```markdown
## v1.1 — 2026-09-11
### Bug Fixes
- **Parent App:** Fixed an issue on small screens.

## v1.0 — 2026-09-10
### New Features
- Initial release.
```

The newest version must be numerically greater than `data/app.json`; the second
must exactly equal that current product version. All history versions must be
unique and descend in `x.y` order. Dates must be valid `YYYY-MM-DD` dates and the
new entry must contain a change bullet. Section headings and the newest entry's
notes become the Debian/PPA changelog, with Markdown styling removed.

The app version becomes the newest history version. The Debian version adds
the next unused PPA suffix: product `1.1` ordinarily becomes
`1.1+ppa1~ubuntu26.04.1`. The publisher checks Launchpad history, including deleted
and superseded sources, fetched public tags, and the existing Debian changelog.
It never replaces tags, force-pushes, or reuses an accepted upload version.

## Unattended operation and approvals

On an already configured development machine, manual execution needs no
administrator approvals. `make publish` asks for explicit confirmation of the
main development pause before release work starts. Declining or EOF stops the
run before signing, pushing or uploading. A retry asks again until the main
update has been durably completed; monitoring an already completed main update
does not ask you to pause again. Status checks have no such prompt. The
publisher runs as the publishing user and invokes neither Polkit nor
`sudo`. Git/SSH and GnuPG run without
interactive prompts. Missing credentials or prerequisites produce a red error;
the publisher never launches setup or falls back to a password dialog.

When an assistant runs it, authorize the single `make publish` process outside
the sandbox at launch if the platform requires approval. Its child commands do
not request additional approvals. This does not override an organization deny
rule or other platform policy. Local test permissions do not grant publication.

One-time prerequisites belong to `./setup.sh --dependencies-only`; the focused
`./setup.sh --ppa-build-tools` mode installs the clean builder. Use the recorded
publisher key, configure GitHub SSH authentication and its known host key, and
set the signing passphrase as a literal assignment in the release checkout's
gitignored `.envrc`, as described under [Noninteractive signing](#noninteractive-signing).
Single-quote values containing dollar signs or backticks. The signer parses the
assignment without executing `.envrc`, sends the value to GnuPG through a private
pipe, and removes signing secrets from build, test, Git and upload environments.
Setup/account provisioning is separate from routine publishing.

## Local publishing tests

`make test-all` and its compatibility alias `make test-all-verify` use metadata-only
VM checks with no whole-image scans. They invoke the
same [`tools/publishing_checks.py`](../tools/publishing_checks.py) utility through
`tools/run-tests publish`. It takes no selectors and performs no signing,
pushes, uploads or Launchpad requests. It needs no publisher credentials.

The utility checks host build prerequisites and version consistency, then freezes
the `PACKAGE_SOURCE_FILES` allowlist in the Makefile into a private
`/tmp/onpc-test-publish-*` snapshot. This includes product code, runtime assets,
licenses, Debian metadata and required build helpers. It excludes development
docs, `tests/`, previews, agent configuration and internal tools. Uncommitted
product edits are included; unrelated edits and their whitespace do not block
packaging. Copying rejects changes to the selected inputs during the snapshot.
When the history announces a newer, dated version, the snapshot receives the
generated app version and changelog. An undated next-version heading is a draft:
local tests retain the current package metadata and print that choice. Actual
publishing still requires the dated release history. After a release, local
tests also use current metadata.
The real checkout is unchanged. The PPA revision is a local candidate; publication
still allocates the unused revision from remote history.

It builds unsigned source, verifies upload manifests and archive contents against
the snapshot, runs source Lintian, builds that DSC in clean resolute/amd64 `sbuild`
with package checks enabled and build network disabled, then runs binary Lintian.
`packaging/check_package.py` validates the selected source formats and release
metadata without requiring development files. The full unit/component suite
runs separately through `make check` and `make test-all`.
The package-input regression builds real source and binary archives with internal
canary files alongside product inputs, including a similarly named user service.
It checks that those files are excluded and customer licenses and manuals remain
installed. Product service installation uses an explicit list even for direct
local builds from the development checkout.
The builder uses unprivileged user namespaces. Failures return nonzero to either
entry point. Source, logs and `result.json` are retained in the printed test/build
directories, and aggregate output appears in the normal `test-all` report.
When invoked by an aggregate, these directories follow its
[last-three-runs retention](../tests/README.md#aggregate-output-retention),
including failed builds. Standalone publishing checks and actual release
operations keep their existing evidence policy.

`make publish` does not invoke this utility, Lintian, version-test targets or
local binary builds, and does not require a saved test result. Run the tests
again when release inputs change. Signed upload integrity, credentials, remote
version uniqueness and publication-state checks remain part of delivery.

## Publication and completion

The publisher validates prerequisites and credentials in the release enlistment,
creates an isolated `/tmp/onpc-release-*` staging checkout, updates the product version and Debian
changelog, and signs the release commit and both version tags. It then:

1. Builds and signs the source upload, verifies the publisher signatures and
   SHA-256 manifests, and checks archived bytes, symlinks and executable modes
   against the signed Git tree. Source uploads use the same product/build
   allowlist as local packaging tests. Integrity verification rejects omitted
   package inputs and any archived files outside that allowlist.
2. Atomically pushes the release commit to its recorded `releases/vX.Y` branch
   and the signed tags,
   verifies public access to the tagged source, and uploads only source artifacts.
3. Automatically cherry-picks the release metadata onto main, pushes main, and
   updates the local main checkout and its remote tracking ref. The highlighted
   **MAIN UPDATED** message releases the development pause.
4. Waits for the exact source, successful amd64 build, binary publication, and
   PPA `Packages.gz` index. It downloads the indexed binary and verifies its size
   and SHA-256 before reporting success in green.
5. Fast-forwards the unchanged release checkout to the release commit,
   including the new app version, changelog and history. Concurrent local edits
   are preserved and reported instead of overwritten. A newer remote main does not prevent release preparation or
   delivery; an existing remote release branch must be an ancestor of the
   prepared inputs, and pushes remain ordinary non-forced fast-forwards.

The PPA must enable only amd64, matching the test module's clean builder. Source
integrity evidence, artifact hashes and `release.json` remain in the reported
release directory. Local publishing tests catch packaging and package-check
failures but cannot guarantee Launchpad availability, account acceptance,
or all installed-app behavior. They do not certify graphical/VM acceptance,
privacy-page content, or human asset/license review; complete applicable release
review before publishing.

The clean builder's `build.log` captures launcher output; detailed package/test
output is retained in its `output/` directory as an sbuild `.build` log. Build
failures report both locations. Package checks run from the reduced unpacked
source archive without `.git`, docs or the development test suite.

Build A/B artifact source fingerprints cover the same package allowlist. Their
fixture payload is a separate test artifact with its own verified digest, never
part of the product package. E2E package preflight compares the package inputs
while retaining a separate full test-input identity for acceptance evidence.

## Bring release metadata back to main

The generated release commit changes `data/app.json` and `debian/changelog`.
Release notes were already committed on main before branching. After the source
push and upload attempt, the publisher prepares a signed cherry-pick in a
temporary clone of the confirmed main checkout. It incorporates remote main
through a fast-forward, pushes the updated main without force, then fast-forwards
the clean local main checkout and refreshes `origin/main`. Existing committed
local main work is included in that push. Uncommitted work, an active Git
operation, a wrong checkout/remote, diverged histories or a cherry-pick conflict
stop the update. Conflicts remain in the retained temporary checkout; the
publisher never starts a cherry-pick operation in the active development tree.

The **MAIN UPDATED** message appears only after local main is clean and agrees
with the fetched remote main. Nothing further is required on main. Its metadata
records the submitted release baseline, not proof of successful publication.
The release checkout monitors and finalizes delivery.
The pause includes source preparation, signing and upload, so it can take
minutes; it does not include waiting for Launchpad to build or publish binaries.

The journal records the main checkout, candidate commit and update phase before
pushing or fast-forwarding. Interrupted updates reuse that exact candidate and
recognize an already accepted main push or completed local fast-forward. Once
the main update is recorded complete, publication retries preserve any new main
development and do not apply the cherry-pick again. If main changes while the
candidate is being applied, the publisher stops rather than overwriting it; preserve the journal
and resolve the reported condition before retrying.

Before preparing the next release, main must contain the preceding release's
metadata. Add the next newer history entry above it, commit the new release
inputs, and create the next release branch. If Launchpad rejects a source or a
build fails, resolve that failure with a newer product release as described
below; preserve the submitted version and tags.

## Retry and recovery

A publishing-only lock in the invoking checkout's private Git directory
(`git rev-parse --absolute-git-dir`) prevents concurrent publishers in that
checkout. `onpc-publish/state.json` there records the checkout identity,
publishing branch, exact source, version, artifacts and phase. Linked worktrees
use their own Git directories, so their journals and publishing locks are
independent of main's. Independent clones also own separate journals and locks.
No development, build, test or repository activity lock is acquired. The main
pause is your confirmed coordination with the publisher, not an enforced lock.
Ordinary
Git operations still take their short-lived Git locks when updating release
refs or checkout indexes; there is no long-lived lock held on main while
building, uploading or monitoring. Main is updated only during the confirmed
handoff and is available for development during monitoring.

Choose one release enlistment for each publication and retain it until
completion. A different clone has no knowledge of an uncertain upload: do not
restart the same release there or copy/delete the journal to bypass recovery.
The atomic non-forced branch/tag push prevents competing prepared attempts
from replacing published refs, but local locks do not coordinate independent
clones. Use `make publish-status` after an interruption to resume monitoring,
including after updating the publishing tool or changing local files, HEAD,
branch, or release notes in that checkout. It only reads the journal and public endpoints; it does
not build, sign, push, upload, update the journal, or fast-forward the checkout.
It can also run alongside a publisher, monitoring the release selected at startup.
Missing temporary build artifacts do not prevent status checks.

For the full publishing workflow, run `make publish` again in the same release
checkout on its recorded branch with its original committed inputs after an
interruption or a repaired local prerequisite. This resumes the
recorded workflow, including checkout finalization. Preserve the printed `/tmp` evidence
directories until completion. Missing or altered frozen artifacts stop the run.
If application fixes are committed or history changes before any public push
was attempted, the next run retains the previous evidence and prepares a fresh
attempt automatically. A durable `push-started` record prevents this replacement
once a source push may have reached the server.

The journal records `upload-started` **before** invoking `dput`. After that point,
an interrupted or failed upload is treated as uncertain: reruns only monitor it
and never upload it again automatically. Status reads tolerate transient service
errors and poll every 30 seconds for up to 24 hours per invocation. A confirmed
build failure is a red error, not a success or an automatic source rewrite.
Each pending check reports its UTC timestamp, elapsed monitoring time,
remaining condition and retry delay. In a terminal, polling replaces one status
line, including transient errors, so the highlighted main-update message stays
visible. The line is shortened to the terminal width to avoid wrapping; redirected
output retains ordinary full log lines. The status line is cleared on success,
failure or interruption. Source acceptance/publication, build
creation/queue/building, binary publication, and package-index propagation have
distinct messages; a completed build is not reported as still pending. Network
errors identify the check that could not be read, without printing response
bodies or private error details. Public reads request HTTP cache revalidation.
Success requires the exact source version, successful amd64 build, matching
binary publication, package-index entry, and downloaded package checksum to
agree. A timeout includes the last observed condition. After editing monitoring
code, stop the old command and run `make publish-status` to load the changes.
Unlike `make publish`, status checks accept a changed release checkout.

If no source appears, inspect Launchpad and the publisher's rejection email.
Resolve confirmed rejection or failed builds before starting a corrected release;
preserve the journal and published source tags as evidence. Do not clear the
journal merely to retry an uncertain upload. A failed source push can be retried
with the same signed refs; no tags are recreated. If the release checkout changed
during publication, preserve that work and restore the recorded release inputs
and branch before resuming local completion. Development on main is independent.
The command does not discard work or roll back public releases.

Before every upload, verify a clean binary build with its declared tests,
inspect the final installed licenses/notices and both front-end About displays,
and confirm that the public privacy page matches the feedback disclosure in
[Compliance.md](Compliance.md). Determine current host/UI/VM acceptance from
[E2E building blocks](TestAutomation/E2E-Building-Blocks.md), recording unresolved coverage rather
than treating historical rehearsal results as acceptance.

## Upgrade acceptance

`make publish` performs the product/version changes itself; do not manually
bump `data/app.json` or `debian/changelog` first. Every release, including a
packaging correction, needs a newer product entry in `VersionHistory.md`.
The publisher chooses an unused PPA revision and creates both signed tags.
Published tags and accepted upload versions are never reused or replaced.

Run `make test-all` or `make test-all-verify` for each new source candidate to
perform source verification and a complete clean binary build. Previously
compiled application output is not reused by the tests. The builder
supports Ubuntu 26.04/resolute on amd64; other Ubuntu releases or architectures
need an explicit tooling extension. Setup need not be repeated for each version.

For installed-user upgrades, additionally verify the previous supported
release upgrading to the candidate, including retained parental settings,
saved-data migration and retries, broker readiness, and the expected activation
level. Test direct upgrades across skipped releases when supported. Follow
[Data migration](SystemDesign/Data-Migration.md) before incompatible reader or
writer changes and [Package update activation](#package-update-activation) for restart,
session renewal and reboot requirements. A normal update does not automatically
require the first installation's reboot.

The [guarded VM runner](../tests/integration/README.md#running-the-current-installed-suite)
has a `--previous-artifacts` route for changed-payload reinstall/reboot checks.
Its current assertions require a reboot and do not establish general
older-version upgrade, no-reboot update or saved-settings migration acceptance.
Use it only for its documented scope; implement missing guarded upgrade cases
when needed and report any remaining release coverage gap. A successful clean
package build alone does not certify those installed-state transitions.

## Bundled asset release checks

These checks belong to the assistant's existing compliance review during
release preparation. The assistant inspects changed assets, checks the final
package for the required license texts and notices, and updates
`debian/copyright` and notices as needed. That file remains the canonical
package license record. Compute any needed file hashes from the release
checkout and include them in release evidence; do not maintain a duplicate
hash table or ask the publisher to collect hashes, repeat the creation
confirmation below, or maintain a separate asset checklist.

Preserve the bundled Quill BSD-3-Clause license, Monocraft SIL OFL-1.1
license and author notice, and Thunderbird branding/MPL-2.0 attribution and
trademark reservation. Review changed assets against their upstream sources
and the canonical records in `debian/copyright`.

Retained source identifiers for future asset reviews:

- **Quill 2.0.3:** [official npm metadata](https://registry.npmjs.org/quill/2.0.3)
  and [tagged source](https://github.com/slab/quill/tree/v2.0.3). The retained
  review matched the four bundled editor files to the npm distribution and
  verified the archive against the registry's SHA-512 integrity value.
- **Monocraft:** upstream commit
  `e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9`, files
  `dist/Monocraft-ttf/Monocraft.ttf` and `LICENSE`, is the
  [reviewed source](https://github.com/IdreesInc/Monocraft/tree/e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9).
- **Thunderbird preview icon:** the [upstream image](https://hg.mozilla.org/comm-central/raw-file/tip/mail/branding/thunderbird/default128.png)
  is a moving reference. The image reviewed on 2026-09-06 has SHA-256
  `64214367f8f8633e3a5be46b18d2bb608d7a76a45cdc5373a5da875013c6d600`.
  Preserve the unmodified icon and its accompanying branding notice in
  corresponding source.

Recheck changed assets and update these identifiers when their sources change;
the retained review does not certify replacements.

The publisher confirmed ChatGPT creation of the product/company logos, kiosk
backgrounds, preview avatars and timer artwork on 2026-09-06. Retain this
provenance record; it does not certify subsequently changed or added assets
or determine copyright protection. No generation-history collection is a
routine release task.

## Recorded publisher details

These are public release metadata, also recorded in
[`tools/publishing/source.py`](../tools/publishing/source.py). Update both places if
the publishing identity changes. Never store a private key, passphrase, access
token, private administrative email, or decrypted confirmation link here.

| Setting | Value |
| --- | --- |
| Publisher display name | `Puffy Slippers Tech LLC` |
| Public Git/changelog email | `dev@tech.puffyslippers.com` |
| Launchpad URL owner / upload identifier | `puffyslipperstechllc` |
| PPA name | `oh-no-parent-control` |
| PPA | <https://launchpad.net/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control> |
| Upload target | `ppa:puffyslipperstechllc/oh-no-parent-control` |
| Publisher OpenPGP fingerprint | `4449F02C3E57F8215261A57958109B593907EFDE` |
| Public source | <https://github.com/Puffy-Slippers-Tech-LLC/parent-control> |
| Git remote | `git@github.com:Puffy-Slippers-Tech-LLC/parent-control.git` |
| Ubuntu series / supported architecture | `resolute` / `amd64` |
| Product version | Read from `data/app.json` at release time |

The display name is not the Launchpad URL owner. The PPA archive signing key
is also distinct from the publisher's source-upload key. Verify prerequisites
and repair only concrete failures. Always query current PPA history before
choosing a version.

## Noninteractive signing

**Never prompt for the signing passphrase, open a passphrase dialog, or ask for
clipboard readiness or another “go ahead,” including on retries.** Read
`APT_PACKAGE_PRIVATE_KEY_PASSPHRASE` from the release checkout's gitignored
`./.envrc` inside the signing process. Manual configuration is described in the
[README](../README.md#set-up-a-development-machine); `setup.sh` does not populate
this value.

Configure `.envrc` locally in the release enlistment before invoking the
publisher, just as on the development checkout. The publisher's isolated
staging clone invokes that enlistment's signer by absolute path; it does not
copy `.envrc` into staging, package source, or release evidence. Gitignore alone
does not exclude a file from `dpkg-source` archives.
Keep the private key in GnuPG's key store and only the passphrase in `.envrc`.

The publisher configures its GnuPG adapter for batch/loopback operation and
supplies the passphrase through a private file descriptor. The value is loaded
only in the signer and kept out of build/test environments, command arguments,
tool output, logs, reports and tracked files. Do not read `.envrc` through a tool
that returns its contents to the conversation. A missing, empty, placeholder or
rejected value produces a redacted configuration error, with no prompt fallback.

This supplies credentials for already-authorized signing; it does not replace
any outstanding publication decision. Sandbox approval boundaries still apply.

Run the local publishing tests to build and inspect source and binary packages
before publishing. The publisher builds and authenticates the signed source
upload. Source archive exclusions are controlled by
`debian/source/options`. Review unexplained Lintian warnings, package contents
and licensing as part of release readiness; do not add blanket overrides.
See [Local PPA validation](Local-PPA-Validation.md) for build evidence and limits.

If a problem is found after upload, investigate and publish a corrected newer
product release. Deleting a PPA publication does not roll back installed packages
or make its version reusable. Preserve the recorded journal and artifacts.

## Confirm publication and deliver the upgrade

The publisher automatically verifies source/build/binary publication and the
downloadable package's indexed size and SHA-256, then records its evidence in
the release report. A source upload or successful build alone is not completion.
Access publisher email only with authorization if rejection details are needed.

After green success, existing PPA subscribers can upgrade with:

```sh
sudo apt update
sudo apt install --only-upgrade oh-no-parent-control
```

Release communications should state the expected activation from the candidate's
manifest comparison: no action, process restart, session renewal, or reboot.
Include user-facing migration requirements and verified coverage limits.

For new Ubuntu 26.04/amd64 computers, provide:

```sh
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo add-apt-repository ppa:puffyslipperstechllc/oh-no-parent-control
sudo apt update
sudo apt install oh-no-parent-control
```

First installation requires a reboot before using child or kiosk sessions.
Existing-user upgrades follow the activation contract below.

## Package update activation

Each Debian package contains `/usr/share/oh-no-parent-control/package-activation.json`. The file lists each activation-relevant installed file, its SHA-256 digest, and the action needed when that file changes. It is generated from the staged package by `packaging/package_activation.py`; it must never be edited by hand.

The install-stage manifest is provisional: `debian/rules` regenerates it through
the [debhelper hook](https://manpages.debian.org/unstable/debhelper/dh.1.en.html#OVERRIDE_AND_HOOK_TARGETS)
`execute_before_dh_md5sums`, after shebang rewriting and ELF stripping. Hashing
only at install time produced digests for unstripped native probe binaries,
not the shipped bytes. `test_final_package_hook_refreshes_stripped_binary_digests`
exercises real stripping, the final hook and its declared debhelper ordering.
Qualification also compares every activation digest against files extracted
from the final Debian package. This package
activation manifest is separate from test-artifact source provenance.

During an APT install or upgrade, `debian/preinst` records that an activation comparison is pending and, for upgrades, saves the manifest from the currently installed package. After unpacking, `debian/postinst` compares that saved manifest with the new one. Added, changed, and removed files all count. The pending marker prevents a later `dpkg --configure` retry from inventing a reboot requirement. A package without a prior manifest is treated as a first installation and requires a reboot, which is conservative for migrations from releases that predate this mechanism.

### Activation levels

| Level | Package action | Reboot marker |
| --- | --- | --- |
| `none` | Nothing | No |
| `process-restart` | Reload systemd and D-Bus, then restart the broker | No |
| `session-renewal` | Reassert child activation through broker startup; the next child or kiosk GNOME session uses updated payloads | No |
| `reboot` | Normal Ubuntu reboot-required marker is created | Yes |

`reboot` is reserved for changes to PAM stack configuration or login-manager/pre-session integration that must activate at a clean login-manager boundary. This includes the kiosk login-check helper as well as the PAM profiles which invoke it. The system GNOME extension payload, kiosk session units, and GNOME session descriptors are `session-renewal`, because an existing graphical session cannot load their replacement safely but the machine does not need to reboot. For this activation level, the package starts the broker, which reasserts extension activation for enabled managed children; a new Shell session loads the updated immutable system payload. Broker code, its systemd unit, and its D-Bus contract are `process-restart`. The packaged fapolicyd fallback rule is also `process-restart`: broker startup regenerates the UID-scoped deny rules and asks fapolicyd to load the resulting aggregate before the broker begins serving requests. Polkit action definitions and administrator-selection rules are `none` because polkitd monitors both directories and loads their changes for subsequent authorization requests. A request-flow update can still require a broker restart or session renewal through its changed broker and child payload files. The display-manager/fapolicyd systemd drop-ins and executable canary are also `reboot`: changes to their fail-closed boot ordering or probe contract need a fresh login-manager boundary.

The compiled `pam_oh_no_parent_control.so` module is `session-renewal`: an
existing PAM transaction can retain its loaded library, while a new login
session uses the replacement. The `session-limit-check` executable is `none`
because PAM executes it afresh for each authentication. The
`execution-policy-ready` executable is also `none`: it checks enforcement
during fapolicyd startup and exits, leaving no resident helper to replace.
Its replacement is used on the next service start. Logging and sanitized error
reporting changes in these files since v1.1 do not change enforcement or boot
ordering and must not request a reboot. Reassess activation if a future change
requires an already-completed readiness check to be repeated; changing that
contract is different from replacing the helper's diagnostics.

Existing v1.1 manifests remain valid: changed files use the new package's
classification, while removed files retain their previous requirement. No
package-version exception or saved-data migration is needed.

The uninstall helper is `none`: it is invoked only while removing the package
and cannot affect an installed update. It is therefore intentionally excluded
from the activation digest manifest even though it is shipped in the package.
The maintainer-script removal guard and execution-policy baseline likewise
activate in the install/remove lifecycle (`none`); they add no running service,
session integration, or saved-preference schema change.

The package never clears `/run/reboot-required` or removes package names from `/run/reboot-required.pkgs`: either may have been created by Ubuntu or another package. It adds its own package name when this package's comparison finds the `reboot` level or after package removal.

For that level, `postinst` invokes Ubuntu's
`/usr/share/update-notifier/notify-reboot-required` package hook with this
package's name. The runtime dependencies include `update-notifier` (the desktop
indicator) and `update-notifier-common` (the hook). Ubuntu owns the restart icon,
tooltip, notification timing, and user notification preferences. The package
does not launch a desktop process from the root maintainer script. If the hook
defers marker creation for Livepatch, `postinst` still records the reboot needed
by our PAM/display-manager integration. Configuration retries avoid duplicate
entries and retain the activation comparison if the hook fails.
`make installdeb` locates the built `.deb`, refreshes APT package indexes, and
copies the package to a temporary `/tmp` file readable by APT's `_apt` user.
It runs ordinary `apt install --reinstall <deb>` on that copy and removes it after
APT exits. This supports checkouts under private home directories without
disabling APT's download sandbox. This staging is specific to installation of a
local build: a published PPA installation downloads the package through APT into
APT-managed storage and never reads the developer checkout. The Makefile change
is part of published source packages, while no binary-package payload or
maintainer-script change is applicable to this path-access condition: APT must
open a local `.deb` before it can unpack or run any code from that package. A
manually downloaded published `.deb` passed to APT from a private directory has
the same caller-side constraint; moving or copying it to an APT-readable path is
necessarily done before package installation.
`make uninstalldeb` runs
`apt remove oh-no-parent-control`. The refresh fails if any configured repository
cannot update, so installation does not retry removed dependency versions from
stale indexes.
Both use only the package payload, installed maintainer scripts, and package
manager integration. They must never add checkout-side setup, cleanup, notices,
or success messages. Installation forces reinstallation of the supplied local
package even when its version is already installed, so rebuilding with the same
version replaces the installed payload. Running frontends must be closed and
reopened to load updated code.
APT installation output is deferred until dpkg finishes configuration and
triggers. `preinst` generates the package-owned
`/etc/dpkg/dpkg.cfg.d/99-oh-no-parent-control-notice`, using dpkg's documented
[`post-invoke` hook](https://manpages.debian.org/unstable/dpkg/dpkg.1.en.html#OPTIONS).
APT starts a new dpkg process for configuration after unpacking, so that
process reads the hook even on the first installation. An APT hook shipped
as a conffile would be too late for the already-running APT process; a dpkg
conffile would likewise become available too late during configuration.

After successful configuration, `postinst` calls the packaged
`/usr/libexec/oh-no-parent-control-package-notice --configured`, which queues a
private completion marker in `/run` when a frontend holds the dpkg lock.
The post-invoke hook reads dpkg's public status fields and waits until this
package is installed and no package remains unconfigured, broken, or awaiting
triggers. It consumes the marker and prints the green PASS line, immediately
followed by the kiosk reboot reminder when this package has an outstanding
reboot request. This places both lines after dependency configuration and
triggers for ordinary APT installs, including `make installdeb`. Failed
configuration retries clear stale completion markers; unrelated later
transactions do not repeat a consumed PASS message. Other independently
configured APT hooks can still emit their own output after dpkg returns.

Direct `dpkg --install` may unpack and configure in a single process, which
cannot load its newly generated hook. Without a frontend lock, `postinst`
therefore retains immediate PASS/reboot output. Removal, purge, and aborted
installation remove the generated hook only if its contents still match;
administrator replacements are preserved. The inline hook checks for the
helper before calling it, so removal of the executable payload is harmless.
The notice helper and generated dpkg configuration activate on invocation
(`none`), are excluded from activation digests, and introduce no saved-data
migration. All of this behavior ships in the `.deb`.

This follows [Ubuntu's package reboot-notification guidance](https://discourse.ubuntu.com/t/ubuntu-deb-package-maintainer-scripts-hooks-triggers-tips-tricks/36174).
The notification wiring activates during package configuration (`none`); it
does not itself change the reboot classifications or saved application data.

The broker remains a static, D-Bus-activated unit. Migration stops it even for an
unchanged reinstall, so every successful configuration requests a broker start;
`process-restart` and `session-renewal` instead request a restart to reassert
policy if a client already activated it. The maintainer script consults
`policy-rc.d` before invoking systemd directly, because `deb-systemd-invoke`
skips inactive static units. A policy denial defers activation; a policy error
or service startup failure fails configuration. Activation comparison markers
are retained on failure for a configuration retry. Debhelper's automatic starts
and upgrade restarts are disabled to avoid a second activation attempt.
These maintainer-script changes activate during package configuration (`none`);
they introduce no boot integration or saved-data migration.

The Fedora-only `oh-no-parent-control-execution-policy-ready.service` is also
`reboot`: it owns the same fail-closed display-manager startup boundary without
adding an `ExecStartPost` command to the Fedora fapolicyd unit.
Its early canary rule template, `00-oh-no-parent-control-canary.rules`, also
uses `reboot` because it defines the boot readiness contract.

### Maintaining classifications

The padded kiosk account icon (`kiosk_account_icon.png`) activates during
package configuration (`none`): provisioning reapplies it through AccountsService.
Its transparent margins keep the artwork inside the login avatar's circular crop.
It introduces no saved-data migration or session payload change.

Removal changes PAM and login-manager integration too. `postrm remove` records
the Ubuntu reboot requirement. The packaged
`/etc/apt/apt.conf.d/99zz-oh-no-parent-control-reboot-notice` uses APT's
[documented `DPkg::Post-Invoke` hook](https://manpages.debian.org/unstable/apt/apt.conf.5.en.html)
to print a removal-specific terminal notice after dpkg and its triggers.
It activates on the next APT invocation (`none`), is excluded from activation
digests, requires no data migration,
and is shared by ordinary APT removal and `make uninstalldeb`.
The command is inline so removal of the executable payload cannot break it.
The conffile remains after ordinary remove, reminding on later transactions
until reboot clears the request or purge removes the hook. Direct dpkg
removal uses Ubuntu's reboot markers without this APT terminal notice.
`postrm` uses the update-notifier hook if present, with a direct marker fallback when
the dependency is missing, fails, or defers notification. Retry does not duplicate
the package entry. A later `postrm purge` does not invent another reboot request;
APT purge of an installed package already runs the removal phase first.

The GDM hook template at `usr/share/oh-no-parent-control/gdm-presession` remains
`reboot`. The generated fallback rule's template at
`usr/share/oh-no-parent-control/99-oh-no-parent-control-allow.rules` remains
`process-restart`. The Polkit rule moved to `usr/share/polkit-1/rules.d` remains
`none`. Ownership records, PAM baseline capture, cleanup guards, and the removal
notice activate in the package lifecycle (`none`). They do not change any saved
preference schema and need no data migration. These packaging changes target
clean installations; they do not adopt untracked installations or accounts.

The native admission gate and witness (`oh-no-parent-control-execution-probe-gate`
and `oh-no-parent-control-execution-probe-witness` under `/usr/libexec`) are
`process-restart`, together with the probe Python adapters and broker runtime
directory declaration. They do not change the boot canary or display-manager
ordering. Their [qualification limits](SystemDesign/Applications.md#pre-exec-admission-for-a-causal-witness)
remain separate from this activation classification.

The `onpc-execution-probe-.service.d/oh-no-parent-control-timeout.conf` system
drop-in supplies the four-second queued-job timeout shared by native probes and
the fixed boot canary. It is `reboot`, because it changes that boot probe's
execution bounds. The production install map includes its final-byte digest;
`test_packaged_probe_dropin_bounds_queued_jobs` and
`test_probe_queue_timeout_add_change_remove_uses_boot_boundary` cover delivery
and activation changes, including removal.

`activation_for()` in `packaging/package_activation.py` is the complete, reviewed mapping from installed path to activation level. `ACTIVATION_MANIFEST_PATHS` in the `Makefile` selects the corresponding installed files for hashing. When adding, moving, or removing a packaged integration file, update both and add a focused unit test in `tests/unit/test_package_activation.py`. Classify by the installed path, not its source directory.

For a normal UI or broker update, do not assign `reboot` merely for caution: the manifest comparison must be able to avoid a reboot prompt. New PAM stack configuration, GDM, or pre-session integration must be classified as `reboot` before it ships. Distinguish those integration changes from replacing a module or short-lived helper that already has a supported activation boundary.

Saved-data migration happens before this activation comparison and has its own retry and failure contract. The migration runner is therefore classified `none`: `postinst` invokes it unconditionally rather than as a later activation action. See [Data migration](SystemDesign/Data-Migration.md#package-lifecycle).
