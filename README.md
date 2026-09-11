[![Oh No! Parent Control logo](data/app_logo.png)](https://tech.puffyslippers.com/oh-no-parent-control/)

[Oh No! Parent Control — app homepage](https://tech.puffyslippers.com/oh-no-parent-control/)

# Developer handbook

Run commands from the repository root on Ubuntu 26.04 Desktop.

## Set up a development machine

```sh
./setup.sh
```

First setup may require administrator authentication. Rerun to refresh dependencies and tooling.

For release signing, create `.envrc` only if absent:

```sh
cp .envrc.example ./.envrc
chmod 600 ./.envrc
```

Set `APT_PACKAGE_PRIVATE_KEY_PASSPHRASE` in `.envrc` from Keeper's “Oh No Parent Control” entry. Keep the value out of `.envrc.example` and version control. See [signing setup](docs/Publishing.md#noninteractive-signing).

| Task | Command |
| --- | --- |
| Refresh dependencies | `./setup.sh --dependencies-only` |
| Install clean PPA build tools | `./setup.sh --ppa-build-tools` |
| Refresh test helpers and policies | `./setup.sh --test-tools-only` |
| Refresh Codex rules | `./setup.sh --codex-rules-only` |
| Show all setup modes | `./setup.sh --help` |

Restart Codex after refreshing rules; trust this checkout.

## Preview while editing

| Preview | Command |
| --- | --- |
| Parent window | `make preview-parent` |
| Kiosk screen | `make preview-kiosk` |
| Shared child request overlay | `make preview-child-overlay` |
| Child extension in nested GNOME Shell | `make preview-child` |

Close the preview or press Ctrl+C to stop. Use **Change Screens** in kiosk/overlay previews to set resolution and scale.

## Build and install locally

```sh
make check-release-version
make build
```

Output: `output/`. Run tests separately; `make build` skips them.

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

Select test files as needed. Quote patterns and parametrized test IDs:

```sh
tools/run-unit-tests tests/unit/test_publish.py -q
tools/run-ui-tests --timeout 180s tests/ui/test_request_form_component.py -q
```

Before direct Make checks that terminate processes, run the cleanup prerequisites below. Proceed only on success. Validated launchers run them automatically.

```sh
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q
```

Reference: [test commands and artifacts](tests/README.md).

## Run VM and graphical E2E tests

Follow [VM setup](tests/integration/Environment.md). Run `./setup.sh --prepare-vm` inside the source guest, then `./setup.sh --prepare-host` on the host. Reuse the accepted baseline.

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

Run `make test-all` for all established regression suites, a colored progress
dashboard, and continuously saved detailed reports under
`docs/TestAutomation/Evidence/test-all-runs/`. Ctrl+C cancels the active test
and waits for owned cleanup. New tests in established suites and E2E variants
marked ready are discovered automatically; unfinished roadmap scenarios are
excluded. See [the regression command](tests/README.md#all-established-regressions).

Use registered E2E scenarios for selected runs. The `make test-fast`,
`make test-system`, and `make test-e2e` aliases are unavailable. References:
[system tests](tests/integration/README.md), [E2E tests](tests/e2e/README.md).

## Publish an app upgrade

Commit application changes on `main`, add the newest release entry to
`docs/VersionHistory.md`, then run:

```sh
make test-all
make publish
```

`make test-all` includes the reusable publishing test module: source checks,
clean Ubuntu sbuild with declared tests, and Lintian. Run `make test-publish`
to execute only that module. `make publish` validates the history, bumps the
version, signs and uploads source, and waits for the package to become
downloadable. It does not rerun the local publishing tests.
See [Publishing](docs/Publishing.md) for one-time credentials, release review,
retained evidence and retry behavior. Routine manual publishing needs no prompts.

To check or resume monitoring an uploaded release:

```sh
make publish-status
```

## Diagnose failures

Logs: `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.log`.

Use `tools/diagnose`; see [diagnostic commands](docs/TestAutomation/Approval-Tools.md). Preserve logs and failed artifacts. Redact personal information before sharing reports.

Check documentation edits with:

```sh
tools/read-only links README.md
git diff --check
```
