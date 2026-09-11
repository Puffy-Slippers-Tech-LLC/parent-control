# Shared test support

Start here before adding fixture code. These are opt-in helpers on top of
pytest, unittest, Hypothesis, Gio, Dogtail and the existing language runners.
Tests own scenarios and assertions; helpers own repeated setup, transport and
cleanup. [Architecture regressions](../unit/test_support_architecture.py) prevent
helpers and test cases from importing collected case modules.

## Find an existing helper

| Need | Reuse | Contract |
| --- | --- | --- |
| Checkout paths and script imports | [paths.py](paths.py), [modules.py](modules.py) | Normal imports use `pyproject.toml`'s `pythonpath`. `load_module(name, path)` loads a fresh standalone script with a unique test-only name; failures restore the registry. |
| Broker configuration and recording adapters | [configuration.py](configuration.py), [broker.py](broker.py) | Fresh mutable state, explicit clocks/callbacks/failures and no OS calls. |
| Unit orchestration without GTK construction | [objects.py](objects.py) | Bind actual class methods to explicit state instead of copying method source. |
| Private D-Bus broker | [dbus.py](dbus.py) | Import `private_service` and call/wait helpers; real Gio serialization on the component suite's private buses, with recording adapters. |
| Preview process lifecycle | [preview.py](preview.py) | `preview_applications` owns only its Popen handles/logs, cleans up failed discovery, attempts every owned child and reports cleanup failures. `tests/ui/conftest.py` owns the compositor and accessibility fixtures. |
| Preview event observations | [events.py](events.py) | `read_events` returns complete JSON-lines records, waits for an unfinished final line, and refuses corrupt complete records. |
| Maintainer-script machines | [package_scripts.py](package_scripts.py), [shell.py](shell.py) | `package_machine` and `machine` execute real scripts against temporary files and explicit command doubles. Path relocation alone is not a sandbox. |
| Terminal and pipe capture | [terminal.py](terminal.py) | `capture` drains output while the child runs, bounds execution and signals only its owned Popen handle. Return codes and terminal color behavior are retained. |
| Graphical Perl helper probes | [perl.py](perl.py) | `run_perl` supplies the maintained library path, captured streams and a deadline. Tests declare their public testapi doubles and assert secret exclusion. |
| Real needle pixel matching | [needle_matcher.py](needle_matcher.py) | `match_image` reuses the installed os-autoinst matcher for GDM and VT6 regressions. Synthetic mutations test refusals; they do not establish live input qualification. VT6 also requires its [exact pixel gate](../e2e/README.md#visible-vt6-installation-terminal). |
| Simulated VM baseline and lease | [vm_baseline.py](vm_baseline.py), [vm_runner.py](vm_runner.py) | Real temporary files and mocked VM operations. Import both `rig` and `lease_rig` when using the latter. Direct simulated `Lease` constructors instead request the explicitly imported `local_preparation_source` fixture, so they hash archived sources without reading the development checkout. JUnit builders retain selected identities and intentional faults. |
| Synthetic E2E evidence and provenance | [e2e_evidence.py](e2e_evidence.py), [e2e_provenance.py](e2e_provenance.py) | `attempt`, `source`, `assets` and `lease` exercise real validators with declared synthetic inputs. |
| Recorder and offline credential fixtures | [e2e_recording.py](e2e_recording.py), [e2e_credentials.py](e2e_credentials.py) | Recorder `session` uses an imported evidence `attempt`; credential `attempt` can be aliased locally. Preserve privacy canaries and cleanup results. |
| Redacted authentication evidence | [authentication.py](authentication.py) | `collect_local` executes the real collector with account/OS reads replaced. |
| Catalog scope and screenshot metadata | [installed_catalog.py](installed_catalog.py), [screens.py](screens.py) | Temporary real catalog discovery; synthetic PNG headers for metadata validation, not pixel acceptance. |
| Child indicator unit adapter | [indicator.mjs](../child/support/indicator.mjs) | Fresh Node VM context and explicit platform doubles; nested-Shell tests retain real lifecycle/input coverage. |
| Nested-Shell input delivery | [mutter_input.py](../ui/mutter_input.py) | Pointer motion, press and release have separate dispatch intervals; pointer and keyboard actions complete the RemoteDesktop session before observation. Failure screenshots retain the pointer to distinguish placement from delivery. |

## Host and guest boundaries

Host support never establishes installed or customer acceptance. Guest execution
uses [system_assertions.py](../integration/system_assertions.py) for real-caller
batches, validated broker replies and authoritative account snapshots, and
[system_accounts.py](../integration/system_accounts.py) for the accepted guarded
identity creation/deletion protocol. The latter refuses collisions and identity
replacement and observes both NSS and AccountsService.

Register guest dependencies in `system_runner.AREA_SELECTED_HELPERS` so selected
staging and source provenance include them. Full selections stage identical
source/target declarations once; conflicting target declarations are refused
before copying files. Reuse the
[installed runner contracts](../integration/README.md#reusable-implementation-contracts)
for live ownership/transport/recovery and the [E2E contracts](../e2e/README.md)
for real graphical input, credentials, private collection and evidence gates.
These development helpers activate on the next invocation; there is no product
integration or saved-data migration.

## Extend without hiding the scenario

Keep expected outcomes, case tables, fault injection and independent oracles in
the owning tests. The broker state-machine model intentionally has independent
state and assertions. Standard `tmp_path`, `monkeypatch`, `unittest.mock` and
`TemporaryDirectory` already supply reusable behavior and need no style wrapper.

Import fixtures explicitly instead of loading every helper as a global plugin.
Include dependency fixtures in the consumer too; aliases can disambiguate names.
Helpers must not import collected cases, mutate the desktop at import time or
infer process ownership from names/environment variables.

Preserve test names, parameter IDs, requirement links, refusal cases, deadlines,
privacy canaries and cleanup checks during extraction. Run affected standalone
selections and complete suites. Cleanup changes require their isolated safety
regressions before protected operations. See [test maintenance](../README.md)
for authorized launchers and evidence boundaries.
