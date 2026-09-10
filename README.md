[![Oh No! Parent Control logo](data/app_logo.png)](https://tech.puffyslippers.com/oh-no-parent-control/)

[Oh No! Parent Control — app homepage](https://tech.puffyslippers.com/oh-no-parent-control/)

# Developer handbook

This README is for developers and maintainers. Run commands from the repository root on Ubuntu 26.04 Desktop.

## Set up a development machine

```sh
./setup.sh
```

Setup installs development/build dependencies, the UI test environment, VM host tooling, and test helpers. First setup may request administrator authentication. Rerun it to refresh the environment.

| Task | Command |
| --- | --- |
| Refresh dependencies | `./setup.sh --dependencies-only` |
| Refresh test helpers and policies | `./setup.sh --test-tools-only` |
| Refresh Codex rules | `./setup.sh --codex-rules-only` |
| Show all setup modes | `./setup.sh --help` |

## Preview while editing

| Preview | Command |
| --- | --- |
| Parent window | `make preview-parent` |
| Kiosk screen | `make preview-kiosk` |
| Shared child request overlay | `make preview-child-overlay` |
| Child extension in nested GNOME Shell | `make preview-child` |

Previews use fixture data and reload supported source/style changes. Close the preview or press Ctrl+C to stop. In kiosk/overlay previews, use **Change Screens** to adjust resolution and scale.

## Build and install locally

```sh
make check-release-version
make build
```

Build output is in `output/`. `make build` skips tests; run the checks below separately.

| Task | Command |
| --- | --- |
| Install the built package on this machine | `make installdeb` |
| Remove the installed package | `make uninstalldeb` |
| Package the child extension separately | `make pack-extension` |
| Install the development extension for the current user | `./setup.sh --install-extension` |

Follow package reboot notices. Log out of the kiosk session before removal; removal retains saved data and logs.

## Run local tests

| Scope | Command |
| --- | --- |
| Baseline: unit/contracts, private D-Bus, syntax and source checks | `tools/run-tests check` |
| Components: private D-Bus, GTK, Node/GJS and nested Shell | `tools/run-tests component-all` |
| Static checks | `tools/run-tests static` |
| Unit, property and contract tests | `tools/run-unit-tests 'tests/unit/test_*.py' -q` |
| Private D-Bus tests | `tools/run-tests component 'tests/component/test_*.py' -q` |
| GTK and nested-Shell tests | `tools/run-ui-tests --timeout 900s tests/ui -q` |
| Child JavaScript | `tools/run-tests child-node` |
| Child GJS | `tools/run-tests child-gjs` |
| Python branch coverage | `tools/run-tests coverage` |
| Requirement mappings | `tools/run-tests traceability stage` |
| Available categories | `tools/run-tests --list` |

Pass specific test files to narrow a run. Quote filename patterns and parametrized test IDs:

```sh
tools/run-unit-tests tests/unit/test_publish_release.py -q
tools/run-ui-tests --timeout 180s tests/ui/test_request_form_component.py -q
```

Validated launchers run required cleanup-safety checks automatically. Before direct Make checks that terminate processes, run these prerequisites and proceed only if they pass:

```sh
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q
```

See the [test contributor guide](tests/README.md) for selection and artifact details.

## Run VM and graphical E2E tests

Prepare the existing test VM using the [VM environment procedure](tests/integration/Environment.md): `./setup.sh --prepare-vm` inside the source guest, then `./setup.sh --prepare-host` on the host. Reuse the accepted baseline for daily runs.

List available cases and build fresh package/fixture inputs:

```sh
tools/run-tests system --list
tools/run-tests e2e --list
tools/run-tests artifacts build
```

Set `ARTIFACT_DIR` to the directory reported by the build, then run the required scope:

```sh
ARTIFACT_DIR='/tmp/onpc-REPLACE-WITH-BUILD-DIRECTORY'
tools/run-tests artifacts verify "$ARTIFACT_DIR"
tools/run-tests system --artifacts "$ARTIFACT_DIR"
tools/run-tests system --artifacts "$ARTIFACT_DIR" --area authorization
tools/run-tests e2e --artifacts "$ARTIFACT_DIR" --scenario E2E-001
```

Keep the checkout unchanged during artifact builds and test attempts. Stop VM maintenance before starting tests. Use `tools/test-vm status` to inspect the pinned VM.

E2E runs only ready scenarios; pending selections refuse execution. The `make test-fast`, `make test-system`, `make test-e2e`, and `make test-all` aliases are not implemented. See the [installed-system runner](tests/integration/README.md) and [E2E runner](tests/e2e/README.md) for current scope and recovery commands.

## Publish a release

Use the [publishing procedure](docs/Publishing.md) for signing-key setup, versioning, tagging, upload, and publication checks.

1. Commit the intended release changes; preparation requires a clean checkout.
2. Plan an unused PPA version and prepare a new isolated release directory:

   ```sh
   python3 tools/publish_release.py plan
   python3 tools/publish_release.py prepare /tmp/onpc-release-UNIQUE
   ```

3. In the prepared `source/` checkout, follow the publishing procedure to commit/tag the release, build with `dpkg-buildpackage --build=binary --no-sign`, run applicable checks, and create the signed source package. Complete the [release compliance checks](docs/Compliance.md).
4. Inspect the signed artifacts:

   ```sh
   python3 tools/publish_release.py inspect /tmp/onpc-release-UNIQUE/source
   ```

5. After release approval, push the reviewed commit and signed tags, then upload the signed source `.changes` using the documented `dput` command. Confirm Launchpad build and publication success.

Use a new directory name in place of `UNIQUE`. Keep signing keys outside the repository. Upload the signed source package to Launchpad; local `.deb` files are for local testing.

## Diagnose failures

Logs: `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`.

Use `tools/diagnose` for system diagnostics and the [approved diagnostic commands](docs/TestAutomation/Approval-Tools.md) for privileged reads. Preserve failed test artifacts and logs; keep personal information out of shared reports.

Check documentation edits with:

```sh
tools/read-only links README.md
git diff --check
```
