# Test maintenance

Start with the [daily testing guide](../docs/Test-Automation.md) for current and
planned commands. This document describes how to select and maintain tests;
it does not repeat completed setup tasks or historical acceptance results.

For unfinished implementation, follow the
[bounded workflow](../docs/TestAutomation/Implementation-Workflow.md): read the
active problem and relevant code, prove one real helper path, then batch its
cases. Preserve a short handoff and clear solved context before a different
problem. A fresh chat does not require rerunning unaffected tests.

## Layers and boundaries

| Location | Purpose | Real dependencies and isolation |
| --- | --- | --- |
| `tests/unit/` | Policy, arithmetic, property/state-machine, adapters, storage, migration, build, runner and source-contract regressions. | Host-safe; controlled doubles are allowed. Tests that launch fixtures still obey process ownership. |
| `tests/component/` | Real broker D-Bus dispatch and serialization on private buses. | Real Gio/GLib transport; injected backend adapters. This is not real installed authorization. |
| `tests/ui/` | Parent, shared request form, feedback UI and nested-Shell component behavior. | Private compositor, D-Bus/AT-SPI/XDG/settings; preview/fake dependencies are declared component inputs. |
| `tests/child/` | Platform-neutral child JavaScript and GJS adapters. | Node and GJS runners; component evidence, not installed GNOME/PAM acceptance. |
| `tests/system/` | Installed package, real caller credentials and OS integration. | Only through the guarded VM runner; excluded from default host discovery. |
| `tests/e2e/` | [Scenario inventory and selection contract](e2e/README.md); graphical execution remains pending. | Host-safe declaration validation is implemented. Future journeys require real product, OS, authentication and guest input, with no mocked outcomes or VM checkpoint shortcuts. |

The current pytest discovery paths and markers are defined in
[pyproject.toml](../pyproject.toml) and [conftest.py](conftest.py). Default pytest
collection includes unit and private-bus components, not the whole product
test matrix. Markers select tests only within the correctly configured runner;
they cannot supply graphical isolation or turn a host process into a guarded
guest. Do not use generic `check-marker`/`check-coverage` as an E2E launcher.

## Cleanup-safety prerequisites

### Approved test and diagnostic categories

Use the [approval tools guide](../docs/TestAutomation/Approval-Tools.md) for the
complete current/future category matrix, validated options, targeted VM control,
read-only system diagnostics, and trust boundaries. Stable entry points are:

```sh
tools/run-unit-tests 'tests/unit/test_*cleanup_safety.py' tests/unit/test_graphical_lease.py -q
tools/run-tests component 'tests/component/test_*.py' -q
tools/run-ui-tests --timeout 360s 'tests/ui/test_*.py' -q
tools/run-tests integration check_graphical_worker
tools/run-tests integration check_package_notice
tools/run-tests system --artifacts /tmp/onpc-test-artifacts/first --area authorization
tools/run-tests e2e --list
tools/diagnose journal --unit 'oh-no-parent-control*' --lines 500
tools/test-vm status
```

`check_package_notice` runs real APT and dpkg against tiny fixture packages in
private chroots under `/var/tmp/onpc-package-notice-*`. It exercises the production
notice bootstrap, helper, and removal hook through first install, reinstall,
remove/reinstall, and trigger failure. It changes no host packages or VM state;
it does not exercise the product's kiosk, PAM, or service provisioning.
Command output and results are retained for the artifact reader below.

Always quote filename patterns and parametrized IDs. The launchers validate
every selection and option, expand globs without a shell, preserve exit status,
and run cleanup prerequisites automatically before host-integrated operations.
Unit/property/contract selections stay in `tests/unit`, components in
`tests/component`, and UI tests in `tests/ui`. Arbitrary pytest config/plugins,
external paths, symlinks, shell commands and Make argument injection are refused.

The root-owned test dispatcher supports integration, system, E2E and pinned-VM
operations. Its Codex approval and Polkit authorization are separate controls.
It trusts the configured checkout's test code and imports. New files within a
supported category need no per-file approvals. Planned E2E and aggregate runners
remain unavailable until implemented; registering an approval is not test
coverage. The updated rules replace broad direct pytest/privileged-reader grants
and restrict relevant old global approvals; use the validated entry points.

Install or refresh with `./setup.sh --test-tools-only`, then restart Codex with
the project trusted. Use `./setup.sh --codex-rules-only` for rule-only updates.
Initial installation uses `./setup.sh --bootstrap-tools` and can require
one-time administrator authentication. Repeated bootstrap and all routine host
setup, including dependencies, use the dedicated `onpc-setup` action and never
fall back to an authentication dialog. Repairing an existing denied installation
requires running that setup mode from an administrator-authorized root session. Installed
Polkit grants permit active local administrators and deny excluded callers;
the new checkout wrappers check permission without requesting authentication.

Temporary screenshot cleanup still uses `tools/cleanup-screenshots` with
explicit caller-owned `/tmp/onpc-*.png` filenames. Privileged graphical smoke
exports still use
`pkexec /usr/local/libexec/onpc-export-screenshot SOURCE /tmp/onpc-new.png`;
the source must be a regular PNG directly inside an
`/tmp/onpc-graphical-smoke-*/testresults/` directory. See the helper's validation
tests for ownership, size/signature and no-overwrite guarantees.

Full `./setup.sh` and `--test-tools-only` both maintain graphical AppArmor policy. Classic VS Code
snap attachment needs anonymous graphics-socket peer rules in libvirtd and
QEMU; the QEMU drop-in activates at the next guest start. Development helpers
activate on invocation (`none`), Polkit watches installed rules, and Codex
requires restart. No product package or saved-data change is involved.

### Prompt-free test artifact access

Use the installed `onpc-test-artifacts` helper for privileged inspection across
all test runs, names, extensions, and nested directories. Its Codex allow rule
and dedicated Polkit rule cover the whole helper, not individual files:

```sh
pkexec /usr/local/libexec/onpc-test-artifacts read /tmp/onpc-system-EXAMPLE/input/selected-inputs.json --bytes 8000
pkexec /usr/local/libexec/onpc-test-artifacts list /tmp/onpc-system-EXAMPLE
pkexec /usr/local/libexec/onpc-test-artifacts tail /tmp/onpc-system-EXAMPLE/private/command-1.log --bytes 16000
pkexec /usr/local/libexec/onpc-test-artifacts stat /tmp/onpc-system-EXAMPLE/evidence/result.json
pkexec /usr/local/libexec/onpc-test-artifacts export /tmp/onpc-future-run/results/recording.webm
```

`read` also accepts `--offset` for paging through large files. `list` returns
JSON names; `stat` returns JSON type, size, mode, and modification time. `export`
prints a new `/tmp/onpc-artifact-export-*/<original-name>` path. Its directory is
mode `700` and file mode `600`, both owned by the invoking account. Ordinary
readers can then inspect the copy without privilege. Existing graphical smoke
PNG exports continue to use `onpc-export-screenshot` above.

Sources may be anywhere beneath `/tmp/onpc-*`, `/var/tmp/onpc-*`,
`/var/tmp/oh-no-parent-control-artifacts`, `/var/log/oh-no-parent-control`, or
this checkout's `tests/`, `artifacts/`, and `output/`. This includes private test
inputs and raw diagnostics for local inspection. Raw exports retain their source
contents; only validated, redacted evidence is suitable for sharing. No sources
are edited, deleted, or made public. Symlink traversal, hard-linked files,
special files, and unrelated host paths are refused. Reads use pinned file
descriptors; exports create new private files without caller-selected write paths.

Use ordinary unprivileged tools for accessible artifacts, this helper for
privileged ones, and the installed test dispatcher for test execution and its
temporary writes. Do not use `pkexec head`, `cat`, `cp`, or an interpreter for
routine artifact work: general root programs have no password-free Polkit grant.
Adding future tests or file formats under these storage roots needs no new rule.

Install or refresh through `./setup.sh --test-tools-only`, then restart Codex
with this checkout trusted to load the new allow rule. Polkit grants activate
immediately for active local `sudo`-group administrators. Installation itself may
need administrator authentication. These development-only helpers activate on
invocation (`none`), are absent from the product package, and change no saved
application data. Restrictive organization-managed Codex policies still take
precedence over local allow rules.

### Manual entry points

Before a host-integrated test that terminates processes, run its cleanup-safety
regressions in isolation. They must pass before the protected operation starts.
For the existing aggregate local/system commands, this cleanup-only selection
covers the current UI, nested-Shell, VM controller and persistent caller paths:

```sh
tools/run-unit-tests \
  tests/unit/test_ui_cleanup_safety.py \
  tests/unit/test_child_preview_cleanup_safety.py \
  tests/unit/test_prepare_host_cleanup_safety.py \
  tests/unit/test_system_runner_cleanup_safety.py \
  tests/unit/test_system_caller_cleanup_safety.py \
  tests/unit/test_system_agent_cleanup_safety.py -q
```

For a focused test, select the safety modules for every cleanup implementation
it uses. New controllers must add their own ownership regressions. The validated
category launchers now run these prerequisites automatically for focused and
aggregate protected operations. Direct legacy Make entry points still require
explicit safety prerequisites.

The developing graphical adapter additionally requires
`tests/unit/test_graphical_lease.py` in isolation before its live use. It covers
VM ownership refusal and real display descriptor transfer/revocation. The
worker adds `tests/unit/test_graphical_worker_cleanup_safety.py`. The privileged
integration dispatcher runs both automatically before
`integration check_graphical_worker`, whose non-VM fixtures verify byte transfer,
normal exit, controller disconnect, and forced supervisor interruption. This
qualifies namespace containment, not the actual os-autoinst/VM integration.

Signal only explicitly spawned, identity-recorded processes. Never infer
ownership from names, environment variables, runtime directories, a host-wide
process scan, or a guessed ancestry relationship. A reused identity must be
refused, not cleaned up. Preserve failed evidence and source logs.

## Local component work

Use `make check-component` for the current component aggregate after its safety
prerequisites. For a focused non-VM UI run, invoke the launcher directly:

```sh
tools/run-ui-tests --timeout 360s tests/ui/test_child_shell_lifecycle.py -q
tools/run-ui-tests --timeout 180s tests/ui/test_request_form_component.py -q
```

Do not inline the launcher's environment or invoke it through another shell.
Both kiosk and child-overlay parameter values remain required for shared-form
changes. Use meaningful accessible names and visible state; do not replace
behavioral tests with checks of widget internals or source strings.

The isolated Dogtail environment is declared in
[ui/requirements.txt](ui/requirements.txt); host tooling comes from
[test-tools-ubuntu-26.04.txt](test-tools-ubuntu-26.04.txt) and `setup.sh`.
Keep versions/hashes there rather than copying dated package tables into docs.
Nested-Shell tests reuse `child/preview-orchestration.sh`, a controlled copy of
the packaged extension, and private runtime state. They must not change the
developer's desktop, extension settings or live source. Preview launchers are
development tools, not customer E2E commands.

Node and GJS checks are available as `make check-child-node` and
`make check-child-gjs`. The latter writes
`artifacts/coverage/gjs-child/coverage.lcov`. Nested-Shell logs and screenshots
are under `artifacts/ui/child-shell/`; `latest/` is only a convenience copy,
never evidence for a different source revision or test attempt.

## Property tests, contracts and coverage

The committed `onpc` Hypothesis profile in `conftest.py` bounds deterministic
generated policy/transaction cases. Turn a discovered failure into a permanent
regression example, preserve its reproducer/profile, and check the real invariant
after each state transition. Do not add a production test mode to support it.

Source/configuration contracts protect supported APIs, ownership, packaging and
architecture. Keep them classified separately from executable customer behavior.
A file assigned the `contract` marker does not become runtime acceptance merely
because pytest executes its assertions.

`make check-coverage` currently reports Python branch coverage for its default
host collection under `artifacts/coverage/` (HTML and XML). It does not report
full graphical/system coverage. Inspect missing paths by security boundary:
caller/target validation, authorization, transactions and rollback, preferences,
migration, enforcement activation and process ownership. A blanket percentage
does not establish those behaviors. Future aggregate evidence must name the
layers actually measured and include the separate child-language results.

## Maintaining regression coverage

1. Identify the changed behavior and its authoritative specification/design
   requirement. Add regression cases at the lowest effective layer and real
   installed/customer coverage when the behavior spans those boundaries.
2. Classify the tests, their affected components/shared dependencies, runner,
   environment and safety prerequisites. Add them to the authoritative suite
   inventory when implemented; they must not be silently absent from `test-all`.
3. Maintain stable `ONPC-...` IDs and `requirements.json`. Run
   `python3 tools/verify_test_traceability.py --mode stage` after specification
   or mapping changes. Current file-existence validation is structural; only
   actual executable evidence justifies `covered`. Supporting contracts cannot
   satisfy a required runtime layer.
4. For graphical work, enumerate and implement the applicable variants under
   [E2E-Coverage.md](../docs/TestAutomation/E2E-Coverage.md). Record the complete
   journey, real actions, visible/backend/other-user assertions, and any declared
   fault or environment intervention. A passing fragment is not a full journey.
5. Run the relevant verification once per ordinary attempt, with bounded waits
   and preserved first failures. Repeated harness qualification is explicit
   maintenance work, not a permanent multiplier in daily commands.
   During implementation, use focused selections and run common checks after
   the stable batch's final edit. Full task verification is an acceptance step,
   not a loop after every diagnostic change. Register canonical cases once
   even when several requirement/task IDs use them; retain every required layer.

Feedback component tests use a fake delivery transport and do not send mail.
Their evidence cannot prove external delivery. Any live delivery test must
declare the actual service, explicit authorization and dedicated test recipient;
never send automated customer journeys to a production support inbox or label
a fake transport as real delivery. The scenario inventory and final audit must
state this boundary explicitly rather than hiding missing external evidence.

Reusable VM/package fixture interfaces are in the
[installed runner guide](integration/README.md). The
[implementation backlog](../docs/TestAutomation/Test-Automation.md) tracks
unfinished automation, not daily procedures.
