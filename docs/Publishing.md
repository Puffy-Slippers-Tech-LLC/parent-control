# First app publication

This is the only entry point needed for the first release. When ready, say:
**“Follow docs/Publishing.md to prepare the first app release, automate the
steps, and present the tested release for publication approval.”**

The assistant handles the following flow:

1. **Choose the release source.** Review current changes and confirm which
   belong in version `1.0` only if the intended inputs are unclear.
2. **Prepare and validate.** Verify existing account/tool setup, select an
   unused PPA version, create an isolated release clone, build and test the
   package, review compliance, and prepare signed source artifacts.
3. **Present the release.** Show the exact version, test results, outstanding
   gaps, and artifacts. Obtain any outstanding readiness/publication decision.
4. **Publish and finish.** Push the source and signed tags, upload to Launchpad,
   monitor the actual build and package publication, and provide installation
   commands and the release report.

Your normal work is resolving ambiguous release inputs, manually configuring
the signing passphrase in the gitignored `.envrc`, and making the release
decision. Account and key setup was reported complete; it is verified, not
repeated routinely.

Automation already exists in `tools/publish_release.py` for version planning,
isolated preparation, source inspection, and source-publication status. The
assistant runs the remaining build, test, signing, push, upload, and monitoring
commands. The helper is not an unattended end-to-end release command.

Before the first upload, verify a clean binary build with its declared tests,
inspect the final installed licenses/notices and both front-end About displays,
and confirm that the public privacy page matches the feedback disclosure in
[Compliance.md](Compliance.md). Determine current host/UI/VM acceptance from
[Test-Automation.md](Test-Automation.md), recording unresolved coverage rather
than treating historical rehearsal results as acceptance.

<details>
<summary>Assistant procedure and command reference</summary>

The assistant executes preparation, checks, builds, signing commands, source
publication and upload as described below, stopping on failures. The publisher
supplies release decisions and maintains the local `.envrc` signing value.
The supported target is Ubuntu 26.04 LTS (`resolute`). Launchpad accepts a
signed source upload and builds the architecture-specific `.deb`; do not upload
the locally built binary package.

Run checkout commands from the repository root on Ubuntu 26.04. The helper
uses only Python's standard library and the tools already installed by
`setup.sh`. No additional host setup is needed solely for this helper.

## Bundled asset release checks

These checks belong to the assistant's existing compliance review during
release preparation. The assistant inspects changed assets, checks the final
package for the required license texts and notices, and updates
`debian/copyright` and notices as needed. That file remains the canonical
package license record. Compute any needed file hashes from the release
checkout and include them in release evidence; do not maintain a duplicate
hash table or ask the publisher to collect hashes, repeat the creation
confirmation below, or maintain a separate asset checklist.

Retained source review from 2026-09-06:

- **Quill 2.0.3:** the four bundled editor files matched the official npm
  distribution byte for byte. The archive matched the registry's SHA-512
  integrity value. Source references are the
  [registry metadata](https://registry.npmjs.org/quill/2.0.3) and
  [tagged source](https://github.com/slab/quill/tree/v2.0.3).
  Preserve the bundled BSD-3-Clause license and copyright notices.
- **Monocraft:** the font and OFL text matched upstream commit
  `e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9`, files
  `dist/Monocraft-ttf/Monocraft.ttf` and `LICENSE`.
  [Pinned source](https://github.com/IdreesInc/Monocraft/tree/e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9).
  Preserve Idrees Hassan's notice and the SIL OFL-1.1 text beside the font.
- **Thunderbird preview icon:** the image and branding notice matched Mozilla's
  upstream files on the review date. Those upstream URLs are moving references;
  the reviewed image SHA-256 is
  `64214367f8f8633e3a5be46b18d2bb608d7a76a45cdc5373a5da875013c6d600`.
  Preserve the accompanying `THUNDERBIRD-BRANDING-LICENSE`, MPL-2.0 attribution,
  Mozilla trademark reservation, and unmodified icon in corresponding source.
  The icon identifies an application in preview data. Ubuntu supplies the full
  license at `/usr/share/common-licenses/MPL-2.0`.
- **Product artwork and former music:** on 2026-09-06, the publisher confirmed
  ChatGPT creation of the then-reviewed product/company logos, kiosk
  backgrounds, preview avatars, timer image, and music. Retain that confirmation
  as the source record; no generation-history collection is a release task.
  It records creation method, without determining copyright protection or
  asserting an unprovided subscription plan or third-party input history.
  The former music was removed on 2026-09-09; request-screen thunder is
  synthesized by project code. The timer image is tracked source but is not
  selected by the extension's installation asset list.

This historical review does not certify subsequently changed or added assets.
The assistant reviews those against the release source and available upstream
evidence as part of the same release preparation.

## Recorded publisher details

These are public release metadata, also recorded in
[`tools/publish_release.py`](../tools/publish_release.py). Update both places if
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
| Ubuntu series / initial architecture | `resolute` / `amd64` |
| Initial product version | `1.0`, read from `data/app.json` at release time |

The display name is not the Launchpad URL owner. The PPA archive signing key
is also distinct from the publisher's source-upload key. A new PPA may not
have an archive signing fingerprint until its first publication.

The publisher reported one-time setup complete on 2026-09-05. Do not ask them
to repeat it. Verify prerequisites and only repair concrete failures. At that
time the public PPA existed and contained no source publications; always query
it again before choosing a version.

## Assistant-led release workflow

This is the primary workflow. The sections below it are command references
and recovery instructions, not a second checklist to run again.

1. **Select source once.** Inspect Git status, branch, remote history and tags.
   Default the initial release to product `1.0` unless the current metadata or
   publisher says otherwise. If there are uncommitted changes, ask which belong
   in the release; review and commit those specific paths after the answer.
   Never silently include ongoing work or use `git add .`. If the checkout is
   clean and its intended release source is clear, do not ask again. Fetch the
   public remote and tags before planning. Resolve divergence before proceeding;
   never force-push or move a published tag.
2. **Check prerequisites.** Verify Ubuntu 26.04/amd64, declared build dependencies
   (`dpkg-checkbuilddeps`), publishing commands (`debuild`, `dput`, `dch`,
   `lintian`), Git push authentication, the recorded signing key's availability,
   and Launchpad registration. Inspect the PPA's enabled architectures and
   ensure only supported architectures are enabled. Use public Launchpad API
   reads wherever possible. A missing tool is a reason to use `setup.sh` or the
   focused `./setup.sh --dependencies-only` mode; do not rerun setup routinely.
   Never request secrets in chat. Use the
   [noninteractive signing procedure](#noninteractive-signing) for GnuPG;
   SSH authentication remains separate.
3. **Prepare automatically.** Run:

   ```sh
   python3 tools/publish_release.py plan
   python3 tools/publish_release.py prepare /tmp/onpc-release-UNIQUE
   ```

   The assistant chooses a new directory name; the publisher need not type it.
   `plan` is read-only. It queries all source publication states, including
   deleted/superseded versions, follows pagination, and considers local tags
   and the changelog. Network/API failure stops planning. `prepare` requires a
   clean development checkout, creates an independent clone at `.../source`,
   configures the public Git identity and signing key locally, and writes the
   next native PPA version into its changelog. Ignored development output is
   not copied. It saves `release.json` beside the clone. It does not commit,
   tag, build, push, or upload. It refuses an existing destination; resume an
   existing release using its recorded checkout instead of preparing over it.
   Check pending uploads from earlier attempts as well: uploads not yet accepted
   may not appear in publication history. Never blindly retry an uncertain upload.
4. **Review and freeze.** Review the changelog and [Compliance.md](Compliance.md).
   Commit the release entry in the clone, then create and verify the signed
   package tag and, for a new product version, the product tag using the commands
   below. Existing product tags are retained for packaging-only rebuilds.
   Record the exact commit and tag fingerprints outside the source checkout.
5. **Build and validate.** Execute the binary build and inspection commands below
   from the release clone, with artifacts in its parent. Run the isolated
   cleanup-safety prerequisites before any protected test/build command. Follow
   [Test-Automation.md](Test-Automation.md) for available host, UI and guarded VM
   validation. Respect any fixed-development-checkout requirements in the
   current test harness; do not rewrite paths or bypass guards to run in the
   release clone. Establish matching source inputs and exact package evidence.
   Do not substitute older test artifacts for the newly versioned package.
   If a clean package build cannot run declared tests on Launchpad, fix that
   packaging/test portability issue before upload; do not silently use `nocheck`.
   Record commands, outcomes, package hashes, environment and coverage gaps in
   a release report beside `release.json`. Comprehensive `test-all` and graphical
   E2E acceptance are currently unfinished: report this explicitly and resolve
   the release-readiness decision with the publisher, without inventing a pass
   or silently starting the test-automation implementation backlog.
6. **Sign and inspect source.** Run the source build below, then:

   ```sh
   python3 tools/publish_release.py inspect /tmp/onpc-release-UNIQUE/source
   ```

   The helper checks source signatures against the recorded publisher key,
   verifies SHA-256 and size for every upload file, checks the package tag's
   commit, compares archived file bytes with Git, rejects extra/duplicate files,
   and runs Lintian. It saves `source-review.json` beside the artifacts. Review
   every excluded tracked file for complete corresponding source, source modes
   and symlinks, Lintian warnings, binary contents and licensing. This helper
   does not replace these reviews or regression acceptance. Keep reports and
   logs outside the clone. Fix unexplained failures before proceeding.
   Before the first upload, also extract this exact signed DSC with
   `dpkg-source -x` into a new directory outside the clone and run
   `dpkg-buildpackage --build=binary --no-sign` there. Keep its parent separate
   from the reviewed artifacts so it cannot overwrite them. This verifies
   declared tests without Git metadata, as Launchpad receives the source;
   a passing build inside a Git clone does not establish that portability.
   Tests that need Git must create their own temporary checkout fixtures, and
   their external commands must be declared in `Build-Depends`.
   Also run `make check-test-fixtures` on the prepared development host. This
   separate acceptance gate runs real Flatpak installation and launch with
   private services and owned processes. Launchpad prohibits the unprivileged
   kernel namespaces required by Flatpak, so its package-build tests verify
   the generated native/Flatpak bundles and native launch; the Flatpak runtime
   check lives in `tests/fixtures/test_runtime.py`. Record both results. Do not
   bypass Flatpak's sandbox or describe the runtime check as passed on Launchpad.
   Use a versioned extraction directory such as
   `build/oh-no-parent-control-1.0+ppa3~ubuntu26.04.1` so checks also exercise
   Debian version punctuation in source paths. Host-safe VM fixtures must
   hash their own archived preparation sources; live VM guards remain pinned
   to the development checkout. Audit test-only Python modules and external
   tools against `Build-Depends`, since a configured development machine can
   hide missing clean-builder dependencies.
   Audit package staging as well as test commands: `_install-product-files`
   invokes `glib-compile-schemas`, so `libglib2.0-bin` must be a build dependency
   even though it is also a runtime dependency. Ppa5 passed all Launchpad tests
   but failed staging when this build dependency was absent. Runtime `Depends`
   does not provision the clean builder. Keep the full binary build, including
   staging and debhelper processing, as the regression acceptance boundary.
7. **Present the concrete release.** Summarize version, source commit/tags,
   architecture, artifact hashes, validation and reviewed warnings/gaps. If
   publication authorization has not already been given for this concrete
   release, ask once to publish the source and upload to the named PPA. Explain
   that this makes the release public and successful builds publish automatically.
   Do all preparation and review before asking; do not ask separate permissions
   for every routine step. Platform sandbox approvals may still be necessary.
8. **Publish and monitor.** Execute the source push and `dput` commands below.
   Explicitly push the release branch to the intended branch, normally
   `git push origin HEAD:main`; the clone's `release/...` branch must not be
   mistaken for `main`. Use a normal fast-forward push; reconcile concurrent
   development before publication if it is refused. Push the signed tags and
   verify their exact source is publicly retrievable before `dput`. Monitor
   the source, every enabled architecture's build, and binary publication:

   ```sh
   python3 tools/publish_release.py status
   ```

   `status` reports source history, not binary acceptance. Follow source API
   links to builds or use the PPA web UI to verify **Successfully built** and
   **Published** for the exact version. An empty result immediately after upload
   is not a rejection or a reason to upload again. Ask the publisher for a
   Launchpad rejection email only if necessary; do not access email implicitly.
   Record the final PPA URL, version, tags and installation commands. Preserve
   artifacts and evidence through completion; a `dput` exit code alone does
   not establish publication.

The normal manual work is choosing release inputs when ambiguous, configuring
the local signing value once, and making any outstanding release decision.
All publisher identifiers are already supplied. Do not publish anything merely
because this guide or its helper is being edited.

## Noninteractive signing

**Never prompt for the signing passphrase, open a passphrase dialog, or ask for
clipboard readiness or another “go ahead,” including on retries.** This replaces
the previous clipboard-readiness requirement. Read
`APT_PACKAGE_PRIVATE_KEY_PASSPHRASE` from the development checkout's gitignored
`./.envrc` inside the signing process. Manual configuration is described in the
[README](../README.md#set-up-a-development-machine); `setup.sh` does not populate
this value.

For isolated release clones, use the original development checkout's `.envrc`
by its absolute path; do not copy it into the clone, package source, or release
evidence. Gitignore alone does not exclude a file from `dpkg-source` archives.
Keep the private key in GnuPG's key store and only the passphrase in `.envrc`.

Before invoking the Git or Debian signing commands below, configure their GnuPG
signer explicitly for batch/loopback operation and supply the passphrase through
a private file descriptor (`--batch --pinentry-mode loopback --passphrase-fd`).
GnuPG does not automatically consume this environment-variable name. Load the
value only in the signer, without shell tracing, and keep it out of build/test
environments, command arguments, tool output, logs, reports and tracked files.
Do not read `.envrc` through a tool that returns its contents to the conversation.
If the file/value is missing, empty, still a placeholder, or rejected, stop with
a redacted configuration error; never fall back to a passphrase prompt.

This supplies credentials for already-authorized signing; it does not replace
any outstanding publication decision. Sandbox approval boundaries still apply.

## One-time publisher setup

Recovery/reference only: skip this section when prerequisite verification passes.

1. Create or sign in to the Launchpad account that will own the archive:
   <https://launchpad.net/+login>.
2. Ensure the email address on the package signing key is confirmed on that
   Launchpad account.
3. Use an existing protected OpenPGP signing key, or create one interactively:

   ```sh
   gpg --full-generate-key
   gpg --list-secret-keys --keyid-format LONG
   gpg --fingerprint
   ```

   Keep the private key in GnuPG's key store and the configured passphrase only
   in the gitignored `.envrc`, never in tracked source. Back up credentials
   using the organization's key-management procedure. Key creation is manual
   account setup; automated release signing follows the noninteractive rule above.
4. Publish the public key to Ubuntu's keyserver, substituting its full
   fingerprint:

   ```sh
   gpg --keyserver hkps://keyserver.ubuntu.com \
       --send-keys 4449F02C3E57F8215261A57958109B593907EFDE
   ```

5. Open the Launchpad account's **OpenPGP keys** page, import that fingerprint,
   decrypt Launchpad's confirmation email, and follow its confirmation link.

   If Thunderbird cannot decrypt the email, use GnuPG directly on the computer
   and under the OS user account where you created or imported the private key
   in step 3. Thunderbird normally uses its own key storage; creating a key
   with `gpg` does not automatically make it available to Thunderbird.

   Copy the encrypted block from `-----BEGIN PGP MESSAGE-----` through
   `-----END PGP MESSAGE-----`, including both marker lines, into a plain-text
   file named `launchpad-confirmation.asc` in your Downloads directory. If the
   email presents the encrypted payload as an attachment instead, save that
   attachment and use its actual path. Decrypt the saved payload with GnuPG's
   `--decrypt` operation through the same noninteractive signer configuration
   above, using the `.envrc` passphrase. Open the resulting confirmation link
   locally and complete confirmation in Launchpad; keep that link out of logs
   and chat. If GnuPG
   reports `decryption failed: No secret key`, check
   `gpg --list-secret-keys --keyid-format LONG` and verify that the private key
   corresponding to the fingerprint submitted in step 5 is available to this
   OS user. Use the computer holding that key or restore it from your secure
   backup; downloading the public key from the keyserver cannot supply the
   private key needed for decryption.

   See [Launchpad's key-import instructions](https://ubuntu.com/docs/launchpad/user/how-to/import-openpgp-key/)
   and [Thunderbird's OpenPGP documentation](https://support.mozilla.org/en-US/kb/openpgp-thunderbird-howto-and-faq).
6. Create a public PPA named `oh-no-parent-control` from the Launchpad web UI.
   Record the exact owner name shown in its URL. For a team-owned PPA, use the
   team's owner name and ensure the signing account has upload permission.
   Enable only architectures on which this application will be supported;
   `amd64` is the initial supported package architecture.
7. Run development setup in the release checkout to configure its public Git
   identity and OpenPGP signing key and install the publishing tools:

   ```sh
   ./setup.sh
   ```

   Setup configures `Puffy Slippers Tech LLC`, `dev@tech.puffyslippers.com`,
   OpenPGP signing, and fingerprint
   `4449F02C3E57F8215261A57958109B593907EFDE` only for this checkout.
   Confirm the public development email on Launchpad and register that key;
   keep the private administrative email out of Git and package metadata.
   Setup does not import the private key. It must be available to the OS user
   creating the signed tags and source upload.

Canonical's current setup instructions are:
<https://documentation.ubuntu.com/project/contributors/new-package/upload-packages-to-a-ppa/>.

## Prepare each release

Manual preparation reference only. The normal assistant workflow uses `plan`
and `prepare` above; do not repeat setup or add another PPA changelog entry
after the helper has prepared the release clone. Continue with source review,
the clean-state checks, commit, and signed tags below. For initial `1.0`, no
product-version bump is needed. When using the helper, read `product` from
`release.json` into `product_version` before creating the product tag.

Automated regression acceptance follows the
[test automation guide](Test-Automation.md). Record evidence for the exact
release source/package and supported environment before publishing. Local
syntax/unit checks or a previously accepted package do not certify a new
release. The comprehensive `make test-all` gate remains planned until its
implementation and full acceptance are complete; do not claim it has run when
only the current focused commands are available. Publisher account/key setup
is separate from daily test execution.

1. Use a dedicated clean release checkout and install the repository-recorded
   development and publishing tools. `setup.sh` installs development
   dependencies, not the product itself:

   ```sh
   ./setup.sh
   ```

2. Export the Debian publisher identity for this terminal. The email must be a
   confirmed address on the Launchpad account. The release command uses this
   identity for the changelog entry:

   ```sh
   export DEBFULLNAME='Puffy Slippers Tech LLC'
   export DEBEMAIL='dev@tech.puffyslippers.com'
   ```

3. Prepare the product release with the repository command. Product versions
   have exactly two components: `x` identifies a major, potentially
   incompatible release and `y` identifies a smaller, compatible update that
   does not change saved-data meaning. The command updates the single
   authoritative release record in `data/app.json` and adds the required
   Debian changelog entry:

   ```sh
   make bump-version VERSION=1.1 CHANGE='Describe the user-visible changes.'
   ```

   The command rejects a reused or decreasing version. Product versions do not
   control saved-data compatibility: follow [Data migration](SystemDesign/Data-Migration.md)
   whenever a code change makes saved application data incompatible.

   The unreleased tree is already initialized at `1.0`; omit this step when
   publishing that initial release without changing its version.
   Also omit it for a packaging-only rebuild of an already published product
   version; increment the PPA revision in the next step instead.

4. Add the PPA build revision to the changelog. This is a `3.0 (native)`
   package, so the package version must not contain a Debian revision separated
   by a hyphen. Derive the product version from its authoritative record rather
   than typing it again. For the first PPA build, use:

   ```sh
   product_version=$(/usr/bin/python3 -c \
       'import json; print(json.load(open("data/app.json"))["version"])')
   ppa_revision=1
   dch --newversion "${product_version}+ppa${ppa_revision}~ubuntu26.04.1" \
       --distribution resolute \
       "Build Oh No! Parent Control ${product_version} for the PPA."
   ```

   Set `ppa_revision` to the next unused integer for another upload of the same
   product version. Never reuse a version already accepted by this PPA, even if
   that publication was later deleted.
5. Review [Compliance.md](Compliance.md), including the source-availability and
   third-party attribution checklist. Publish the exact source tags before the
   public PPA upload, as described below.
6. Commit the release state and confirm there are no uncommitted or untracked
   files:

   ```sh
   make check-release-version
   git diff --check
   git status --short --untracked-files=all
   ```

   The status command must produce no output. Git status does not report
   ignored files by default, and `dpkg-source` does not use `.gitignore` as its
   archive exclusion list. Review `git status --short --ignored` and
   `debian/source/options`; keep unrelated files and prior build artifacts
   outside this checkout. In particular, the ignored `output/` directory is
   not excluded by the current source options.
7. Create a signed tag for this exact Debian package version:

   Git forbids `~` in reference names. Replace it with `_` in the source tag
   only: package `1.0+ppa1~ubuntu26.04.1` maps to tag
   `v1.0+ppa1_ubuntu26.04.1`. The helper uses the same mapping.

   ```sh
   version=$(dpkg-parsechangelog -S Version)
   source_tag="v$(printf '%s' "$version" | tr '~' '_')"
   git tag -s "$source_tag" -m "Oh No! Parent Control ${version} source"
   git verify-tag "$source_tag"
   ```

   For the first upload of a new product version, also create its signed
   product tag:

   ```sh
   product_tag="v${product_version}"
   git tag -s "$product_tag" -m "Oh No! Parent Control ${product_version}"
   git verify-tag "$product_tag"
   ```

   A packaging-only rebuild retains the existing product tag and receives a
   new package-version tag. If inputs change before publication, commit the
   correction, recreate only the affected unpushed tags, and repeat validation.
   Never move a pushed tag; use a new version and tag for a correction.

8. Build and inspect the binary package using the next section.

## Build and inspect a local binary

The package is architecture-specific because it contains a PAM shared object.
Launchpad must build that object independently for every published
architecture.

If prerequisite checks found missing build dependencies, install them through
`./setup.sh --dependencies-only`. Then build without root privileges:

```sh
dpkg-buildpackage --build=binary --no-sign
```

The `.deb`, `.changes`, and
`.buildinfo` files are written to the parent of the source directory. Inspect
the actual version and architecture rather than assuming an artifact name:

```sh
version=$(dpkg-parsechangelog -S Version)
architecture=$(dpkg-architecture -qDEB_HOST_ARCH)
changes="../oh-no-parent-control_${version}_${architecture}.changes"
deb="../oh-no-parent-control_${version}_${architecture}.deb"
test -f "$changes" && test -f "$deb"
lintian "$changes"
dpkg-deb --info "$deb"
dpkg-deb --contents "$deb"
sha256sum "$deb"
```

## Create and inspect the signed source package

Set shell variables to the publisher-specific values, then build the signed
source upload:

```sh
launchpad_owner='puffyslipperstechllc'
ppa_name='oh-no-parent-control'
signing_key='4449F02C3E57F8215261A57958109B593907EFDE'

make check-release-version
test "$(dpkg-parsechangelog -S Distribution)" = resolute
debuild -S -sa -k"$signing_key"
```

After a successful source build, inspect the upload artifacts:

```sh
version=$(dpkg-parsechangelog -S Version)
source_changes="../oh-no-parent-control_${version}_source.changes"
source_dsc="../oh-no-parent-control_${version}.dsc"
source_archive="../oh-no-parent-control_${version}.tar.xz"
test -f "$source_changes" && test -f "$source_dsc" && test -f "$source_archive"
gpg --verify "$source_changes"
gpg --verify "$source_dsc"
lintian "$source_changes"
tar -tf "$source_archive"
sha256sum "$source_changes" "$source_dsc" "$source_archive"
git status --short --untracked-files=all
test "$(git rev-parse HEAD)" = "$(git rev-parse "${source_tag}^{commit}")"
```

Verify both signatures belong to the registered publisher key. Review the
native source tarball for complete corresponding source and unintended files,
including local build output, credentials, and other generated artifacts. The archive
exclusions are controlled by `debian/source/options`, as described in the
[dpkg-source manual](https://manpages.debian.org/testing/dpkg-dev/dpkg-source.1.en.html).
Keep all files listed by `_source.changes` together in the parent directory;
`dput` uploads the files referenced there.

Do not continue if the source build, signature, or Lintian review reports an
unexplained error. Warnings must either be fixed or reviewed and documented;
do not add blanket Lintian overrides.

Ubuntu 26.04's packaged Lintian may report `newer-standards-version 4.7.4`
because its local policy table still identifies 4.7.3 as current. The package
intentionally declares 4.7.4 after review against Debian Policy 4.7.4.1. This
specific warning is reviewed; do not lower the field merely to silence an
older Lintian data file. Recheck the current policy before each release:
<https://www.debian.org/doc/debian-policy/>.

## Publish the source and upload

After artifact review passes, publish the release commit
and the signed package-version tag to the public source repository:

```sh
git push origin HEAD:main
git push origin "$source_tag"
```

For a new product version, also push its product tag:

```sh
git push origin "$product_tag"
```

Confirm the exact tags and corresponding source are publicly accessible at the
location in [Compliance.md](Compliance.md#product-license-and-corresponding-source).
Then upload the reviewed signed source package:

```sh
dput "ppa:${launchpad_owner}/${ppa_name}" "$source_changes"
```

This changes a public archive: successful builds may be published automatically
and become available to existing PPA subscribers immediately.
If a problem is found after upload, stop promotion, investigate, and publish a
corrected newer package version. Deleting a PPA publication does not roll back
packages already installed by consumers or make its version reusable.

Launchpad's upload instructions are:
<https://documentation.ubuntu.com/launchpad/user/how-to/packaging/ppa-package-upload/>.

## Confirm publication

1. Watch the PPA package page and the publisher's email for upload rejection or
   build failures. Confirm that the `resolute` source and every enabled
   architecture show **Successfully built** and then **Published**.
2. Open the published source entry and verify that its version equals the local
   `debian/changelog` version.
3. Record both source and product tags alongside the published PPA version.
4. Publish these consumer commands:

   ```sh
   sudo apt update
   sudo apt install software-properties-common
   sudo add-apt-repository universe
   sudo add-apt-repository ppa:puffyslipperstechllc/oh-no-parent-control
   sudo apt update
   sudo apt install oh-no-parent-control
   ```

Canonical's consumer instructions are:
<https://documentation.ubuntu.com/launchpad/user/how-to/packaging/ppa-install/>.

## Publish an update

For every update, create a new changelog entry and a strictly newer unique
package version, create a new signed package-version tag, rebuild and inspect
both binary and signed source artifacts, upload the new `_source.changes`, wait
for publication. Follow [Package-Update.md](Package-Update.md) when
deciding whether changed integration requires a process restart, session
renewal, or reboot.

If saved-data meaning changes, ship the migration required by
[Data migration](SystemDesign/Data-Migration.md).

</details>
