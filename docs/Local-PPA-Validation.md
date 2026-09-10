# Clean local PPA validation

Run the entire binary package build locally before uploading its source to
Launchpad. Ubuntu recommends [sbuild for local package builds](https://ubuntu.com/project/docs/contributors/building/build-packages-locally/)
and its [unshare backend](https://ubuntu.com/project/docs/contributors/setup/set-up-for-ubuntu-development/#sbuild)
on current Ubuntu releases. Docker is optional; the clean dependency environment
is what catches failures concealed by a configured development machine.

The ppa5 failure illustrates the gap: its tests passed, but staging failed at
`glib-compile-schemas` because `libglib2.0-bin` was missing from `Build-Depends`.
Runtime `Depends` does not install tools in a package builder.

## Setup and repeated builds

On an existing development machine, refresh the dispatcher once for this new
setup operation, then install the tools:

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

Use this command for every later release as well as the initial publication.
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
data migration and activation. See [subsequent releases and upgrade acceptance](Publishing.md#subsequent-releases-and-upgrade-acceptance)
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

## Verified run — 2026-09-10

The existing `1.0+ppa6~ubuntu26.04.1` source from
`/tmp/onpc-release-20260910-ppa6/source` completed a real clean build with
sbuild `0.91.2ubuntu3`. Evidence is retained at
`/tmp/onpc-ppa-check-c0vglp0e`; sbuild's timestamped log is under `output/`.
The attempt used an independent copy of the source artifacts and did not alter
the active publishing session's clone, version, tags or uploads.

- Sbuild reported `Status: successful`, total package time **244 seconds**,
  dependency installation **95 seconds**, and binary build **120 seconds**.
- **6,675 unit tests** and **58 component tests** passed before staging and
  final `.deb` creation. The package metadata was independently read back as
  `oh-no-parent-control`, `1.0+ppa6~ubuntu26.04.1`, `amd64`.
- DSC SHA-256: `0ad5c96147da2f4caf385de4bbb53739615c331e25dd2ef45edd3934694f8c52`.
- Source archive SHA-256: `98eb1a222ff4e4a5bd3736ab5c0afe37735a76cc46cc19750e0e032dbb4e4d36`.
- Binary SHA-256: `363a916a177eb5412f6de88632ce5408fa6fe6e5db40269927a12de22466d112`.
- **236 focused tooling tests** passed for launcher/rule boundaries, source
  checksums, result handling, secret/environment exclusion and setup retry/failure
  behavior. Shell static checks, Markdown links and whitespace checks passed.

The final wrapper additionally requires nonempty expected `.deb` and binary
`.changes` files and records their hashes before reporting success. That guard
was added while this first build ran; its success/missing-output/failure cases
passed focused tests, and this run's actual output presence, metadata and hashes
were verified separately. The first run's JSON therefore contains input hashes;
subsequent runs also record output hashes.

Development helpers and Codex rules were installed through `setup.sh`. Restart
Codex to use the new preapproval. The concurrent `First-Release-Handoff.md`
changes belong to the publishing session. These tooling changes remain in the
working tree for source review; no source commit or publication was made here.
