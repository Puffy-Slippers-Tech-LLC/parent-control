# Clean local PPA validation

`make test-publish` tests source packaging and a clean local binary build.
`make test-all` includes that same [publishing test utility](../tools/publishing_checks.py),
which calls the [clean build module](../tools/publishing/build.py). `make publish`
delivers the release without rerunning these local tests.

Ubuntu recommends [sbuild for local package builds](https://ubuntu.com/project/docs/contributors/building/build-packages-locally/)
and its [unshare backend](https://ubuntu.com/project/docs/contributors/setup/set-up-for-ubuntu-development/#sbuild).
Runtime `Depends` does not install tools in a package builder; all build and
staging tools must be declared in `Build-Depends`.

## Setup and repeated builds

If build prerequisites are missing, install them through:

```sh
./setup.sh --ppa-build-tools
```

Full `./setup.sh` also installs these prerequisites on a clean machine. The
focused mode installs `sbuild`, `mmdebstrap`, `uidmap` and Ubuntu archive keys,
preserves unrelated configuration and the test VM, and can be safely repeated.
Use standard packaged namespace support; never disable host security restrictions
to make the builder run. The test module reports missing prerequisites without
installing anything.

For each new release candidate, prepare the application changes, add the new
`docs/VersionHistory.md` entry, and run:

```sh
make test-publish
```

Use `make test-all` to run this alongside all established suites. These commands
include uncommitted changes in a private source snapshot, require no signing
credentials, and never push or upload. Each invocation builds fresh source and
binary artifacts. Commit the application changes and run `make publish` when
ready to release; see [Publishing](Publishing.md) for its separate requirements.

Each build attempt creates a new `/tmp/onpc-ppa-check-*` directory containing
`input/`, `output/`, `build.log`, the effective sbuild configuration and
`result.json`. The report includes input/output hashes and exit status. During a
build, live progress is in the timestamped `.build` file under `output/`;
`build.log` may be buffered until completion. Logs remain on failure; read them
with `tools/read-only` or ordinary unprivileged readers. Evidence is retained.
Sbuild cleans its own temporary build environment.

The test utility verifies unsigned upload manifests and the archive against its
frozen snapshot before the builder checks the DSC/archive size and SHA-256 and
copies the exact input bytes. The publisher separately authenticates signed
release artifacts at delivery time.
It accepts only this project's native source package and resolute PPA version
format. Working-tree edits are included when the snapshot is created; later
edits require another test run.

The build uses an amd64 host, Ubuntu resolute, standard archive components,
declared build dependencies, no Git checkout, and no skipped tests. Dependency
downloads precede the build; the build's network is disabled. Full staging and
debhelper processing must succeed. A dedicated sbuild base cache accelerates
retries; each build starts a fresh environment and resolves dependencies.
Custom system sbuild configuration is refused because it can introduce host
hooks or extra packages. User flags, signing secrets and custom hooks are not
inherited.

## What a pass establishes

This catches missing dependencies, archived-source assumptions, test portability
issues, downloads during compilation, and failures in package staging,
permissions, library analysis and binary creation. It does not fully reproduce
Launchpad's package versions, enabled archive dependencies, kernel restrictions
or worker configuration. Remote failures can still require investigation.

The publisher separately verifies signatures, archive eligibility, version reuse,
upload checks, successful remote builds and downloadable binary publication.
Neither a local nor a Launchpad build replaces license/payload review, guarded VM
installation tests or the Flatpak runtime gate. Run `make check-test-fixtures`
on the prepared development host for the separate Flatpak runtime acceptance;
Launchpad's kernel restrictions prevent running that gate there. Installed-user
upgrades additionally require checks for retained settings, data migration and
activation. See [upgrade acceptance](Publishing.md#upgrade-acceptance).

## Approval scope

`make test-publish` runs unprivileged on a configured host; namespace support and
dependency downloads can require execution outside an assistant's sandbox.
An assistant needs separate authorization for publication through `make publish`.
Local test permissions do not grant signing, pushing or uploading.
See [Approval tools](TestAutomation/Approval-Tools.md#publishing).

This development tooling has activation `none`: no installed service change,
customer data migration or reboot is introduced.
