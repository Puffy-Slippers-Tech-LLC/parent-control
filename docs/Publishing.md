# Publishing to a Launchpad PPA

These are the manual steps that require the publisher's Launchpad identity,
OpenPGP private key, release decision, or permission to change a public archive.
The supported target is Ubuntu 26.04 LTS (`resolute`). Launchpad accepts a
signed source upload and builds the architecture-specific `.deb`; do not upload
the locally built binary package.

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
   Record the exact owner name shown in its URL. Enable only architectures on
   which this application will be supported and tested; `amd64` is the initial
   supported package architecture.
7. Configure the release checkout to use the same confirmed identity and key,
   substituting the publisher's values:

   ```sh
   git config user.name 'PUBLISHER NAME'
   git config user.email 'CONFIRMED_LAUNCHPAD_EMAIL'
   git config user.signingkey 'FULL_OPENPGP_FINGERPRINT'
   ```

Canonical's current setup instructions are:
<https://documentation.ubuntu.com/project/contributors/new-package/upload-packages-to-a-ppa/>.

## Prepare each release

1. Install the repository-recorded development and publishing tools:

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
   control saved-data compatibility: follow `Data-Migration.md` whenever a
   code change makes saved application data incompatible.

   The unreleased tree is already initialized at `1.0`; omit this step when
   publishing that initial release without changing its version.

4. Add the PPA build revision to the changelog. This is a `3.0 (native)`
   package, so the package version must not contain a Debian revision separated
   by a hyphen. Derive the product version from its authoritative record rather
   than typing it again. For the first PPA build, use:

   ```sh
   product_version=$(/usr/bin/python3 -c \
       'import json; print(json.load(open("data/app.json"))["version"])')
   dch --newversion "${product_version}+ppa1~ubuntu26.04.1" \
       --distribution resolute \
       "Build Oh No! Parent Control ${product_version} for the PPA."
   ```

   Increment `ppa1` for another upload of the same product version. Never reuse
   a version already accepted by this PPA, even if that publication was later
   deleted.
5. Review `Compliance.md`, including the source-availability and third-party
   attribution checklist.
6. Commit the release state and confirm there are no uncommitted or untracked
   files:

   ```sh
   git status --short
   ```

   This command must produce no output. The release must not be built from a
   dirty checkout.
7. Create the signed product-version tag locally, but do not push it until the
   uploaded package passes acceptance:

   ```sh
   git tag -s "v${product_version}" \
       -m "Oh No! Parent Control ${product_version}"
   ```

   If any release input changes after this point, delete and recreate the
   unpushed local tag after committing the correction. Never move a tag that
   has already been pushed.

8. Build and inspect the binary package using the next section. A release build
   must not set `DEB_BUILD_OPTIONS=nocheck`.

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

For packaging development only, a build can omit the test phase using Debian's
standard `nocheck` option:

```sh
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage --build=binary --no-sign
```

Never use `nocheck` for a release candidate. The `.deb`, `.changes`, and
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

Install and exercise the local package only in a disposable Ubuntu 26.04 VM.
It provisions an account and integrates with PAM, GDM, fapolicyd, systemd,
D-Bus, Polkit, and GNOME sessions. A first installation intentionally creates
Ubuntu's reboot-required marker.

## Create and upload the signed source package

Set shell variables to the publisher-specific values, then build the signed
source upload:

```sh
launchpad_owner='YOUR_LAUNCHPAD_OWNER'
ppa_name='oh-no-parent-control'
signing_key='FULL_OPENPGP_FINGERPRINT'

make check-release-version
debuild -S -sa -k"$signing_key"
version=$(dpkg-parsechangelog -S Version)
source_changes="../oh-no-parent-control_${version}_source.changes"
test -f "$source_changes"
lintian "$source_changes"
dput "ppa:${launchpad_owner}/${ppa_name}" "$source_changes"
```

Do not continue if the source build, signature, or Lintian review reports an
unexplained error. Warnings must either be fixed or reviewed and documented;
do not add blanket Lintian overrides.

Ubuntu 26.04's packaged Lintian may report `newer-standards-version 4.7.4`
because its local policy table still identifies 4.7.3 as current. The package
intentionally declares 4.7.4 after review against Debian Policy 4.7.4.1. This
specific warning is reviewed; do not lower the field merely to silence an
older Lintian data file. Recheck the current policy before each release:
<https://www.debian.org/doc/debian-policy/>.

Launchpad's upload instructions are:
<https://documentation.ubuntu.com/launchpad/user/how-to/packaging/ppa-package-upload/>.

## Confirm publication

1. Watch the PPA package page and the publisher's email for upload rejection or
   build failures. Confirm that the `resolute` source and every enabled
   architecture show **Successfully built** and then **Published**.
2. Open the published source entry and verify that its version equals the local
   `debian/changelog` version.
3. On a clean, disposable Ubuntu 26.04 Desktop VM, install from the public PPA:

   ```sh
   sudo add-apt-repository universe
   sudo add-apt-repository \
       "ppa:${launchpad_owner}/${ppa_name}"
   sudo apt update
   apt-cache policy oh-no-parent-control
   sudo apt install oh-no-parent-control
   ```

4. Confirm `apt-cache policy` selects the intended PPA version. Reboot when the
   package requests it, then verify the required services and login integration:

   ```sh
   systemctl is-active fapolicyd.service
   systemctl is-active oh-no-parent-control-broker.service
   grep -F 'pam_oh_no_parent_control.so' /etc/pam.d/common-auth
   grep -F 'oh-no-parent-control-session-limit-check' /etc/pam.d/common-account
   test -x /usr/libexec/oh-no-parent-control-login-check
   test -r /usr/share/wayland-sessions/oh-no-parent-control.desktop
   ```

   Open the Parent application as an administrator and save a test child's
   screen-time and application policy. Confirm that the child session enforces
   it, that the child overlay can submit a request, and that the dedicated
   **Oh No! Parent Control** login session can submit a request. Perform this
   acceptance only with disposable test accounts and data.
5. After the PPA artifact has passed acceptance, push the commit and the signed
   source tag created earlier. The tag names the product version, not the PPA
   revision:

   ```sh
   git push origin HEAD
   git push origin "v${product_version}"
   ```

6. Publish these consumer commands, replacing the owner if necessary:

   ```sh
   sudo add-apt-repository universe
   sudo add-apt-repository ppa:YOUR_LAUNCHPAD_OWNER/oh-no-parent-control
   sudo apt update
   sudo apt install oh-no-parent-control
   ```

Canonical's consumer instructions are:
<https://documentation.ubuntu.com/launchpad/user/how-to/packaging/ppa-install/>.

## Publish an update

For every update, create a new changelog entry and a strictly newer unique
package version, rebuild and inspect both binary and signed source artifacts,
upload the new `_source.changes`, wait for publication, and test an APT upgrade
from the previously published version. Follow `Package-Update.md` when deciding
whether changed integration requires a process restart, session renewal, or
reboot.
