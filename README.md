[![Oh No! Parent Control logo](data/app_logo.png)](https://tech.puffyslippers.com/oh-no-parent-control/)

[Oh No! Parent Control — app homepage](https://tech.puffyslippers.com/oh-no-parent-control/)

# Developer handbook

Run commands from the repository root on Ubuntu 26.04 Desktop.

Routine authorized work runs unattended after setup. The repository-wide
[approval tools guide](docs/Approval-Tools.md) covers reads, edits, builds,
tests, diagnostics, setup and publishing, including the rare cases that need
human authorization.

## Set up a development machine

```sh
./setup.sh
```

First setup may require administrator authentication. Rerun to refresh dependencies and tooling.

Full setup and `--dependencies-only` include the offline GUI-fixture build
prerequisites: Flatpak, Snap packaging, SquashFS, Python/GTK introspection,
DejaVu fonts and XKB keyboard data. Tests report missing prerequisites and do
not install them. Fixture builds produce temporary payloads; they do not install
the product or a fixture Snap on the development host.

For VM tests and release signing, create `.envrc` only if absent:

```sh
cp .envrc.example ./.envrc
chmod 600 ./.envrc
```

Set `APT_PACKAGE_PRIVATE_KEY_PASSPHRASE` in `.envrc` from Keeper's “Oh No Parent Control” entry. Keep the value out of `.envrc.example` and version control. See [signing setup](docs/Publishing.md#noninteractive-signing).

Also set `TEST_ACCOUNT_PASSWORD` to your chosen password for all four VM test
accounts. Baseline preparation and E2E tests require this literal assignment
in the private `.envrc` file; neither uses an environment-variable fallback.
You can use the same password to log in manually. Do not commit it or put the
real value in `.envrc.example`.

| Task | Command |
| --- | --- |
| Refresh dependencies | `./setup.sh --dependencies-only` |
| Install clean PPA build tools | `./setup.sh --ppa-build-tools` |
| Refresh test helpers and policies | `./setup.sh --test-tools-only` |
| Refresh Codex rules | `./setup.sh --codex-rules-only` |
| Show all setup modes | `./setup.sh --help` |

Full setup and `--test-tools-only` install the `tools/watchvm` desktop identity,
supplied app logo and refreshed icon cache for the viewer's dock icon.
Run it at any time to see the guarded VM screen, SSH output and current operation
across tests, setup and maintenance. Closing it leaves VM work running.

Restart Codex after refreshing rules; trust this checkout.

## Preview while editing

| Preview | Command |
| --- | --- |
| Parent window | `make preview-parent` |
| Kiosk screen | `make preview-kiosk` |
| Shared child request overlay | `make preview-child-overlay` |
| Child extension in nested GNOME Shell | `make preview-child` |

Close the preview or press Ctrl+C to stop. Use **Change Screens** in kiosk/overlay previews to set resolution and scale.

To watch automated UI tests, open `tools/watch-ui` at any time. **All branches**
shows concurrent UI workers in a 2×2 grid; each worker also has its own tab with
the current test and phase. It follows `tools/run-ui-tests` and every
`tools/run-tests` selection that includes UI work, including `ui`, `host` and
`all`. Closing and reopening the viewer leaves the tests running. The viewer
receives only copied frames and cannot send keyboard, pointer or resize input
to tests. It can stay open between runs; capture starts with the UI fixture, so
already-running workers from before this feature need a new test run.

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
| Selected UI scope in up to four branches, with cleanup prerequisites | `tools/run-tests ui -m 'not live_e2e'` |
| Focused unit, property and contract tests | `tools/run-unit-tests tests/unit/test_publish.py -q` |
| Private D-Bus tests | `tools/run-tests component 'tests/component/test_*.py' -q` |
| Focused GTK and nested-Shell tests | `tools/run-ui-tests --timeout 180s tests/ui/test_request_form_component.py -q` |
| Child JavaScript | `tools/run-tests child-node` |
| Child GJS | `tools/run-tests child-gjs` |
| Python branch coverage | `tools/run-tests coverage` |
| Requirement mappings | `tools/run-tests traceability stage` |
| Complete established regressions | `tools/run-tests` or `tools/run-tests all` |
| All host tests and package qualification, four branches, no VM | `tools/run-tests host` |
| Sequential installed-system and GUI E2E VM tests | `tools/run-tests system e2e` |
| Usage and `all` composition | `tools/run-tests --help` |
| Available categories | `tools/run-tests --list` |

`host + system + e2e = all`. Any combination is accepted; host runs first,
then system and E2E sequentially, sharing package inputs and one report.
`tools/run-tests host system e2e` is equivalent to `all`.

Match validation scope to the change: prefer `tools/run-tests ui` for UI-only
coverage and `tools/run-tests unit` for unit-only coverage, with selectors as
needed. Use `host` only when all host checks are justified. Unit/UI selections
share the aggregate's module buckets and four-branch scheduler, without adding
package stages or unrelated suites. UI retains its mandatory cleanup prerequisites.
See the [scheduling contract](tests/README.md#all-established-regressions).
Keep the direct launchers below for narrow iteration or diagnosis.

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

Follow [VM setup](tests/integration/Environment.md). With the source VM off, run
`tools/prepare-baseline` on the host. It validates `.envrc` first, prepares the
guest accounts and reusable tools during a controlled boot, then captures the
powered-off guest. Existing accounts keep their UIDs and homes; their password,
picture, display name, role, shell and unlocked status are reconciled with the
fixture definitions. Existing keyrings are backed up so GNOME can create ones
matching the shared password. Repeating this command replaces the baseline
without restoring it. Ordinary `./setup.sh` never prepares a baseline.

For manual maintenance, restore your own snapshot (for example `1 - Clean`),
make your changes, shut down the VM, and replace your snapshot as usual. Then
run `tools/prepare-baseline`. It accepts the current disk chain of the same VM
without another confirmation, preserves your snapshots, and replaces only the
automation-owned `onpc-baseline`. It never restores a snapshot during preparation.

For an explicitly authorized replacement after manual baseline deletion, prepare
and shut down the guest, then run `./setup.sh --replace-missing-baseline`. This
retains the old controller record and validates the new guest before capture.

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

`make test-all` runs all established tests with metadata-only VM snapshot verification.

`make test-all-verify` is a compatibility alias for `make test-all`. All VM operations use metadata checks; none scans whole VM images.

Both commands show a colored progress dashboard and continuously save detailed reports under
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
make test-all-verify
make publish
```

Both test commands include the reusable publishing test module: source checks,
clean Ubuntu sbuild with declared tests, and Lintian. `make publish` validates the history, bumps the
version, signs and uploads source, and waits for the package to become
downloadable. It does not rerun the local publishing tests.
See [Publishing](docs/Publishing.md) for one-time credentials, release review,
retained evidence and retry behavior. Routine manual publishing needs no prompts.

To check or resume monitoring an uploaded release:

```sh
make publish-status
```

## Diagnose failures

Structured logs: `/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.events`.
Feedback exports render these as readable dated `.log` files alongside
`system-info.json`; legacy text logs are not collected. See
[logging and feedback](docs/SystemDesign/Logging-and-Feedback.md).

Use `tools/diagnose`; see [diagnostic commands](docs/Approval-Tools.md#system-reads). Preserve logs and failed artifacts. Redact personal information before sharing reports.

Check documentation edits with:

```sh
tools/read-only links README.md
git diff --check
```
