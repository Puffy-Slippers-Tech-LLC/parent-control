# Clean local PPA validation

Run the entire binary package build locally before uploading its source to
Launchpad. Ubuntu recommends [sbuild for local package builds](https://ubuntu.com/project/docs/contributors/building/build-packages-locally/)
and its [unshare backend](https://ubuntu.com/project/docs/contributors/setup/set-up-for-ubuntu-development/#sbuild)
on current Ubuntu releases. Docker is optional; the clean dependency environment
is what catches failures concealed by a configured development machine.

Runtime `Depends` does not install tools in a package builder; all build and
staging tools must be declared in `Build-Depends`.

## Setup and repeated builds

If prerequisites are missing, refresh the development helpers and install the
build tools through setup:

```sh
./setup.sh --test-tools-only
./setup.sh --ppa-build-tools
```

Full `./setup.sh` also installs the prerequisites on a clean machine. The focused
mode installs `sbuild`, `mmdebstrap`, `uidmap` and Ubuntu archive keys, preserves
the test VM and unrelated configuration, and can be safely repeated. Use the
standard packaged namespace support; never disable host security restrictions
to make the builder run. The build command reports missing prerequisites rather
than installing packages on the host itself.

Restart Codex in the trusted development checkout to load the maintained rules.
From that checkout, after preparing and inspecting the release source:

```sh
tools/publish-release check-build /tmp/onpc-release-UNIQUE/source
```

When working elsewhere, use the absolute development-checkout launcher. Each
call creates a new `/tmp/onpc-ppa-check-*` directory containing `input/`,
`output/`, `build.log`, the effective sbuild configuration and `result.json`.
The report includes input/output hashes and the exit status. During a build,
sbuild's live progress is in the timestamped `.build` file under `output/`;
`build.log` may be buffered until completion. Logs remain on failure;
read them with `tools/read-only` or ordinary unprivileged readers. There is no
automatic deletion of evidence. Sbuild owns and cleans its temporary build
environment. No global process cleanup or Docker/VM operation is performed.

The helper accepts only this project's native source package and resolute PPA
version format, verifies the archive size and SHA-256 from the DSC, and copies
the exact input bytes before building. Signature and signed-Git-tree validation
remain the separate `inspect` step in [Publishing](Publishing.md). Changes made
after source creation require rebuilding the DSC; the command deliberately does
not build unarchived working-tree edits or silently choose a new release version.

The build uses an amd64 host, Ubuntu resolute, standard archive components,
declared build dependencies, no Git checkout, and no skipped tests. Dependency
downloads precede the build; the build's network is disabled. Full staging and
debhelper processing must succeed. A dedicated sbuild base cache accelerates
retries; each build still starts a fresh environment and resolves dependencies.
Custom system sbuild configuration is refused pending review because it can
introduce extra packages or host commands. User build flags, signing secrets
and custom hooks are not inherited.

## What a pass establishes

Use this command for every release candidate.
It reads the version from the selected release's changelog, so later PPA
revisions and product versions such as `1.1` and `2.0` use the same command and
approval rule. Prepare new source artifacts for each candidate. The build
remains a complete clean build even when the product changes are small; only
the base environment is cached. Setup need not be repeated for each version.

This catches many missing dependencies, archived-source assumptions, test
portability issues, attempts to download during compilation, and failures in
package staging, permissions, library analysis and final binary creation.

It is not a complete local copy of Launchpad. Archive package versions, enabled
PPA dependencies/pockets, architecture, kernel restrictions and Launchpad worker
configuration must be compared when a remote-only failure remains. Additional
architectures require their own qualified builds; this command only covers
resolute/amd64. Upload authentication, signatures, version reuse, quota, archive
acceptance and publication are separate checks. Keep the existing Lintian,
license/payload review, guarded VM installation tests and Flatpak runtime gate.
Neither this command nor a Launchpad build replaces those runtime checks.
Installed-user upgrades also need old-to-new checks for retained settings,
data migration and activation. See [upgrade acceptance](Publishing.md#upgrade-acceptance)
for version planning and the current guarded VM coverage limits.

## Approval scope

The maintained `tools/publish-release` allow rule covers preparation, inspection,
public status and clean local builds, including future build-and-fix retries.
It grants no general Python, shell, sbuild or Docker execution. The wrapper
validates its arguments; a prefix rule alone cannot validate trailing options.
General source editing and the existing project test helpers retain their
already-authorized routes. Signing and remote publication stay with the active
publishing session and its existing authorization.

Rules load on Codex startup; installing them does not update an already-running
session. See [Approval tools](TestAutomation/Approval-Tools.md#release-preparation-and-inspection).
These are development tools with activation `none`; no customer data migration,
product service restart or reboot is introduced.
