# Fedora Workstation 44 packaging

This is a development target for local VM testing and future COPR use, not a
release-qualified platform. The functional acceptance baseline remains Ubuntu
26.04/GNOME 50. Fedora installation is restricted to Workstation 44, and the RPM
requires GNOME Shell 50 and Malcontent 0.14 or newer. Fedora 44 supplies
[Malcontent 0.14](https://packages.fedoraproject.org/pkgs/malcontent/malcontent/fedora-44.html)
and [GNOME Kiosk 50](https://packages.fedoraproject.org/pkgs/gnome-kiosk/gnome-kiosk/fedora-44.html).

## Shared packaging authority

The [Makefile](../Makefile) owns one source allowlist and one payload map. Local
Debian builds, Launchpad source preparation and RPM source preparation freeze
that same allowlist. Developer files, test tooling, secrets and repository
metadata are excluded. Both formats use `data/app.json` for the product version;
the Debian changelog supplies the shared source timestamp. RPM's packaging
release is a separate build counter, not another product version.

The [shared lifecycle templates](../packaging/lifecycle/preinst.in) own account
ownership, execution-policy baselines, migration exclusion, provisioning,
activation and removal. The [Ubuntu](../packaging/ubuntu.inc) and
[Fedora](../packaging/fedora.inc) adapters supply OS-specific commands and paths.
The [renderer](../packaging/render_lifecycle.py) embeds standalone shell in both
formats: pre-install and post-removal do not need an installed Python helper.
Debian's small wrappers are expanded after `dh_installdeb`, preserving its
original debhelper boundary.

The formats also share [source checks](../packaging/check_package.py), the
[activation classifier](../packaging/package_activation.py),
[manuals](../packaging/man/oh-no-parent-control.1), assets, modules, native
helpers and security templates. Both refresh activation digests after stripping
and shebang rewriting, against final shipped bytes. Manual installation and the
child-command alias belong to the shared payload map; each format applies its
normal compression. Shared source checks validate the rendered lifecycle shell
for both distributions. The
[RPM spec template](../rpm/oh-no-parent-control.spec.in) supplies dependency
names, native PAM paths, metadata and transaction callbacks. Launchpad signing,
upload and monitoring stay in the existing [publisher](Publishing.md).

## Local builds

`make build` starts both binary formats concurrently from one frozen source
generation, with separate working copies. Debian outputs, including debug
packages, `.changes` and `.buildinfo`, go to `output/deb/`. RPM sources, rendered
spec, input fingerprint, SRPM and binary RPMs go to `output/rpm/`. A failed
backend makes the command fail after both workers finish; successful artifacts
from the other backend remain.

Full `./setup.sh` and `./setup.sh --dependencies-only` install the Ubuntu build
prerequisites, RPM tools and rootless Podman, then prepare a caller-owned Fedora
44 build image. An existing development host can prepare just the RPM path with
`./setup.sh --rpm-build-tools`. Refresh installed setup helpers first with
`./setup.sh --test-tools-only` when upgrading a checkout that predates this mode.

The [container recipe](../rpm/Containerfile) uses Fedora's official 44 image and
installs the spec's `BuildRequires` through
[DNF builddep](https://dnf5.readthedocs.io/en/latest/dnf5_plugins/builddep.8.html).
Its local image tag fingerprints the recipe and build dependencies; changes to
either require repeating setup. Podman needs the invoking user's normal
subordinate UID/GID mappings and permitted rootless container execution.
Setup reports missing host prerequisites and preserves unrelated configuration.

Binary builds use native Fedora 44 `rpmbuild`, a configured noninteractive Mock
builder for `fedora-44-x86_64`, or the prepared Podman image on Ubuntu. Container
builds run without networking or image pulls, with dropped capabilities and only
their private RPM workspace mounted. The build never installs dependencies.
Fedora binaries are compiled against Fedora libraries. The image is a development
builder, not installed-system qualification or a Mock/COPR acceptance result.
Host preparation follows [the setup contract](Approval-Tools.md#one-time-setup).

| Scope | Command |
| --- | --- |
| Both binary formats, in parallel | `make build` |
| Debian alone | `make build PACKAGE_FORMAT=deb` |
| Fedora RPM and SRPM | `make build-rpm` |
| SRPM only | `make srpm` |
| Tarball, fingerprint and spec without RPM tools | `make rpm-source` |
| Next development RPM build counter | `make build RPM_RELEASE=0.2.dev` |

The default RPM release is `0.1.dev`; increase it when distributing another local
build with the same product version. Source-only preparation never claims a
binary build. A missing `rpmbuild` still leaves the tarball, fingerprint and
spec under `output/rpm/`. Native/container build output is retained in
`output/rpm/build.log`, including failures. A successful binary build must produce
the product RPM. `make install` is the sole checkout product installation entry
point. Its internal `installdeb` module reads the current version's package from
`output/deb/`. Its internal `installrpm` module selects the most recently modified binary
product RPM in `output/rpm/`, excluding source and debug packages, and uses
DNF to install it and resolve missing dependencies from enabled repositories.
An equal installed version is reinstalled from the local RPM; an older or newer
installed version is replaced by the selected build. RPM queries inspect the
package identity without privilege; only the DNF transaction uses `sudo` for
non-root callers. `make install` detects the
distribution through `os-release` and dispatches to the DEB or RPM module;
package lifecycle compatibility checks still apply. This target installs the
app on the calling machine and are not development build or validation commands.

The RPM is the installation authority. Its `Requires` resolve runtime
dependencies and its embedded scriptlets perform all product configuration,
including service accounts, PAM, provisioning, service activation and reboot
notices. The internal `installrpm` module only selects the local artifact, checks whether that
exact version needs reinstalling and invokes DNF. Installing the same RPM
directly with DNF or from COPR must perform the same setup without a checkout or
any Make-side repair. Local same-version rebuilds explicitly use DNF reinstall;
normal COPR upgrades use increasing RPM releases.

## Fedora lifecycle

Fedora uses `wheel` for the Parent launcher and broker group, `/etc/gdm` for the
generated PreSession hook, and `/usr/lib64/security` for x86_64 PAM. The shared
launchers retain their private Python tree at `/usr/lib/oh-no-parent-control`.
Fedora's MATE Polkit agent uses its foreground
[/usr/libexec executable](https://packages.fedoraproject.org/pkgs/mate-polkit/mate-polkit/fedora-44.html).
Kiosk provisioning rejects `sudo`, `adm` and `wheel` membership on either OS.

The [Fedora PAM helper](../packaging/fedora_pam.py) uses the public
[authselect custom-profile interface](https://github.com/authselect/authselect/blob/master/src/man/authselect.8.adoc).
It copies the active profile into an owned custom profile, retains selected
features and inserts a stack generated from both shared PAM profiles with
the administrator group substituted. The kiosk gate precedes the session-limit
profile's account skip rules. It never uses `--force`, replaces local
PAM edits or disables `without-nullok` to accommodate the passwordless kiosk.
Modified ownership/profile records and reserved-profile collisions fail visibly.
Removal restores the original profile/features before module deletion.

RPM `%pre` maps instance counts to install/upgrade and stops/excludes the broker
before unpack. `%posttrans` runs migration and configuration after dependencies.
A failure preserves migration/activation records. Unlike dpkg, RPM may still
record that package as installed; resolve the cause and retry configuration as
root through the installed script:

```sh
/bin/sh '/usr/share/oh-no-parent-control/lifecycle/postinst' configure
```

Final erase runs shared enforcement/PAM cleanup in `%preun`; upgrade removal
callbacks return immediately. A failed `%preun` attempts shared abort-remove
restoration and returns failure. `%postun` performs the remaining owned account,
integration and baseline cleanup after payload erasure and systemd reload.
Native RPM erase retains preferences/logs. The package also ships the explicit
`sudo oh-no-parent-control-purge [--yes]` action. It loads trusted standalone
shared cleanup before DNF5 erases its payload, uses the supported
[`--no-autoremove` option](https://dnf5.readthedocs.io/en/latest/commands/remove.8.html),
verifies exact package absence and restored active PAM, then completes shared
guarded cleanup before deleting product state/logs. No checkout is needed.
Post-erase failures retain ownership records for resolution; RPM cannot restore
erased payload automatically. Reinstall the package normally from its RPM or
repository, resolve the conflict and repeat the packaged command to retry; the
same reinstall restores the command after ordinary removal. See the
[shared removal/purge contract](SystemDesign/Package-Removal.md#remove-purge-and-retry).
These differences require live upgrade/removal/purge testing.

Configuration restores ordinary SELinux labels for generated integrations and
keeps SELinux enforcing. A package marker under `/run` repeats the kiosk reboot
reminder until reboot. Fedora needs no Ubuntu update-notifier dependency.
Reminders never reboot or log users out.

Fedora's package trust filter permits `.js` but excludes `.mjs` under `/usr/share`,
while fapolicyd classifies the child ES modules as JavaScript and its language
policy requires trust. The shared [package lifecycle](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle)
installs narrowly scoped supplemental trust from the shipped module hashes and
refreshes the daemon before activation. This is distribution-independent package
integration, also applied to Ubuntu; it neither widens Fedora's trust filter nor
adds an allow rule. SELinux labels are restored before the daemon consumes the file.

Fedora runs the shared execution canary in the independent
`oh-no-parent-control-execution-policy-ready.service`. The display manager
requires and orders itself after this oneshot gate, which requires fapolicyd;
configuration also starts the gate and fails if it cannot complete. It
is preceded by rule compilation and a rules-only reload during configuration,
so a daemon already running before installation receives the new canary rule
before the broker starts.
The owned `00-oh-no-parent-control-canary.rules` contains only the fixed
root-canary deny, ordered before Fedora's default trusted-file execute allow.
It preserves the distribution and administrator rules; modified or substituted
owned canary files block replacement/removal. Its template is tracked as `reboot`.
The gate has a 90-second startup timeout and restarts with fapolicyd through `PartOf`.
It has no runtime-directory ownership and does not add `ExecStartPost` to
fapolicyd: systemd must not prepare the daemon's SELinux-labelled runtime files
for an unrelated helper. SELinux remains enforcing without additional policy
grants. Ubuntu retains its existing fapolicyd `ExecStartPost` integration.
Changes to this Fedora boot gate require a reboot through the activation manifest.
Removal reloads systemd after deleting the display-manager dependency, then
stops any retained readiness service or clears its failed state before restoring
the execution-policy baseline. This preserves the running desktop and prevents
a reinstall from reusing a pre-removal readiness result. Upgrade erasure skips
this cleanup; the replacement package owns configuration. The owned canary rule
is removed before rebuilding the remaining policy or restoring the baseline.

## Local VM qualification

Both registered distributions are enabled in the default test queue. Enabling
Fedora schedules its checks; it does not establish a passing result or release
qualification. The shared installed runner includes platform-aware package,
authorization, enforcement and removal checks. Its `removal` area performs one
install/configure/remove/reboot/health/reinstall history using the same
behavioral assertions on DEB and RPM; see the
[installed suite](../tests/integration/README.md#running-the-current-installed-suite).
Public GUI journeys and their exact provider bindings need separate Fedora
qualification. Historical Ubuntu-only acceptance does not transfer to Fedora.

Fedora's
[default known-libs policy](https://src.fedoraproject.org/rpms/fapolicyd/raw/f44/f/fapolicyd.spec)
loads a [trusted-file execute allow](https://github.com/linux-application-whitelisting/fapolicyd/blob/v2.0.1/rules.d/42-trusted-elf.rules)
before `89-oh-no-parent-control.rules`. The broker now also writes concrete
UID-scoped path/hash denials to `01-oh-no-parent-control-deny.rules`, ahead of
those distribution allows. Wildcard allowances remain late to preserve
distribution language/library restrictions. This ordering is shared with Ubuntu;
it changes neither distribution rule files nor trust filters. Installed
enforcement qualification remains required before Fedora acceptance.

Use `tools/prepare-appsnapshot --vm NAME --y` for a configured, pinned Fedora
Workstation 44 VM with a finalized baseline. The shared preparation path builds
the actual RPM, installs it with DNF, reboots and verifies the exact package and
configured services before capturing the app snapshot. SELinux remains enforcing.
Online mode leaves an owned running guest for `tools/test-vm --vm NAME exec -- COMMAND`;
`tools/test-vm --vm NAME stop` restores its outer baseline. This preparation does
not replace the Ubuntu acceptance baseline or establish Fedora release qualification.

Qualify fresh install; kiosk ownership and confinement; administrator discovery
and authentication; time/app enforcement; both request surfaces; boot readiness;
upgrade migration/activation; failed-configuration retry; removal and reinstall.
Include edited-PAM/integration refusal and logged-in-kiosk removal refusal.
Keep SELinux enforcing and preserve denial evidence. Source checks and a passing
package build do not establish these installed behaviors.

## Future COPR publication

The committed [.copr/Makefile](../.copr/Makefile) implements COPR's documented
[SCM `make srpm` method](https://docs.copr.fedorainfracloud.org/user_documentation.html#scm).
It uses the local SRPM builder and COPR's supplied `outdir`, without uploads or
credentials. The recipe installs only Python and RPM build tools inside COPR's
disposable source-build chroot before invoking the shared builder. This remote
recipe is separate from local development setup; do not run it on the host.
Its invocation and failure handling have a local regression using command doubles;
an actual COPR build remains future qualification.
Configure the repository root as the SCM subdirectory, this source
method and `rpm/oh-no-parent-control.spec.in` as the recipe path. Pin an approved
commit/tag and restrict chroots to `fedora-44-x86_64`. Uploading a local SRPM is
an alternative with the same frozen inputs.

Before publishing, complete native/Mock binary validation and Fedora VM
acceptance, choose the owner/project and packaging release, review the generated
spec/source fingerprint, and obtain publication authorization. Project creation,
tokens, webhooks, repository/signing policy and uploads remain future release
work. Neither `make build` nor this recipe creates a COPR project or release.
