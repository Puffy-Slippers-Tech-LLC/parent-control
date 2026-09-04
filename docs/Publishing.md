# Publishing to a Launchpad PPA

These are the manual steps that require the publisher's Launchpad identity,
OpenPGP private key, release decision, or permission to change a public archive.
The supported target is Ubuntu 26.04 LTS (`resolute`). Launchpad accepts a
signed source upload and builds the architecture-specific `.deb`; do not upload
the locally built binary package.

Run checkout commands from the repository root on Ubuntu 26.04, in the same
shell. Replace uppercase placeholders
before running commands. Run each build and inspection step separately and stop
on failure; the snippets are not an unattended publishing script.

## One-time publisher setup

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

   Keep the private key and its passphrase out of this repository. Back them up
   using the organization's key-management procedure.
4. Publish the public key to Ubuntu's keyserver, substituting its full
   fingerprint:

   ```sh
   gpg --keyserver hkps://keyserver.ubuntu.com \
       --send-keys FULL_OPENPGP_FINGERPRINT
   ```

5. Open the Launchpad account's **OpenPGP keys** page, import that fingerprint,
   decrypt Launchpad's confirmation email, and follow its confirmation link.
6. Create a public PPA named `oh-no-parent-control` from the Launchpad web UI.
   Record the exact owner name shown in its URL. For a team-owned PPA, use the
   team's owner name and ensure the signing account has upload permission.
   Enable only architectures on which this application will be supported;
   `amd64` is the initial supported package architecture.
7. Configure the release checkout to use the same confirmed identity and key,
   substituting the publisher's values:

   ```sh
   git config user.name 'PUBLISHER NAME'
   git config user.email 'CONFIRMED_LAUNCHPAD_EMAIL'
   git config gpg.format openpgp
   git config user.signingkey 'FULL_OPENPGP_FINGERPRINT'
   ```

Canonical's current setup instructions are:
<https://documentation.ubuntu.com/project/contributors/new-package/upload-packages-to-a-ppa/>.

## Prepare each release

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
   export DEBFULLNAME='PUBLISHER NAME'
   export DEBEMAIL='CONFIRMED_LAUNCHPAD_EMAIL'
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
   control saved-data compatibility: follow [Data-Migration.md](Data-Migration.md)
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

   ```sh
   version=$(dpkg-parsechangelog -S Version)
   source_tag="v${version}"
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

Install the declared build dependencies, then build without root privileges:

```sh
sudo apt update
sudo apt build-dep .
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
launchpad_owner='YOUR_LAUNCHPAD_OWNER'
ppa_name='oh-no-parent-control'
signing_key='FULL_OPENPGP_FINGERPRINT'

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
git push origin HEAD
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
4. Publish these consumer commands, replacing the owner if necessary:

   ```sh
   sudo apt update
   sudo apt install software-properties-common
   sudo add-apt-repository universe
   sudo add-apt-repository ppa:YOUR_LAUNCHPAD_OWNER/oh-no-parent-control
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
[Data-Migration.md](Data-Migration.md).
