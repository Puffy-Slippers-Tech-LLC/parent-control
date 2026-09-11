# Clean local PPA validation

`make publish` builds the exact signed source package locally before uploading it
to Launchpad. The [publisher](../tools/publish.py) calls the
[clean build module](../tools/publishing/build.py) automatically; there is no
separate preparation or build launcher.

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
to make the builder run. Publishing reports missing prerequisites without
installing anything.

For each new release candidate, commit the application changes, add the new
`docs/VersionHistory.md` entry, and run:

```sh
make publish
```

This command includes signing and public publication after validation succeeds.
See [Publishing](Publishing.md) for credentials, source requirements and recovery.
Rerun the same command to resume a recorded release; successful local build
evidence is reused only for its unchanged, frozen source.

Each build attempt creates a new `/tmp/onpc-ppa-check-*` directory containing
`input/`, `output/`, `build.log`, the effective sbuild configuration and
`result.json`. The report includes input/output hashes and exit status. During a
build, live progress is in the timestamped `.build` file under `output/`;
`build.log` may be buffered until completion. Logs remain on failure; read them
with `tools/read-only` or ordinary unprivileged readers. Evidence is retained.
Sbuild cleans its own temporary build environment.

The publisher verifies source signatures and the signed Git tree before the
builder checks the DSC/archive size and SHA-256 and copies the exact input bytes.
It accepts only this project's native source package and resolute PPA version
format. Changed source inputs require a new candidate; unarchived working-tree
edits are never included.

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

Manual `make publish` needs no prompts on a configured host. An assistant must
have authorization for the complete publication and may need one outer process
approval at launch. Local test permissions do not grant signing, pushing or
uploading. See [Approval tools](TestAutomation/Approval-Tools.md#publishing).

This development tooling has activation `none`: no installed service change,
customer data migration or reboot is introduced.
