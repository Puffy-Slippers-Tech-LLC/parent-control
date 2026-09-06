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
| `tests/e2e/` (planned) | Complete graphical customer journeys and declared real fault/recovery scenarios. | Real product, OS, authentication and guest keyboard/mouse. No mocked outcomes or VM checkpoint shortcuts. |

The current pytest discovery paths and markers are defined in
[pyproject.toml](../pyproject.toml) and [conftest.py](conftest.py). Default pytest
collection includes unit and private-bus components, not the whole product
test matrix. Markers select tests only within the correctly configured runner;
they cannot supply graphical isolation or turn a host process into a guarded
guest. Do not use generic `check-marker`/`check-coverage` as an E2E launcher.

## Cleanup-safety prerequisites

### Approved privileged test categories

`setup.sh` installs a root-owned `/usr/local/libexec/onpc-test-runner`, bound
to this checkout. Use these entry points for Codex privileged test runs:

```sh
pkexec /usr/local/libexec/onpc-test-runner integration check_graphical_worker
pkexec /usr/local/libexec/onpc-test-runner system --artifacts /tmp/onpc-test-artifacts/first --area authorization
```

The integration category accepts any direct `tests/integration/check_*.py`
file with a lowercase alphanumeric/underscore name and no script arguments.
Future checks need no individual approval. Helpers, arbitrary paths, symlinks,
and arbitrary command arguments are refused. The system category accepts the
runner's artifact path, area/test selectors, listing and qualification flag.
The launcher runs all `tests/unit/test_*cleanup_safety.py` modules and
`test_graphical_lease.py` as the invoking user before executing the selected
test as root. New cleanup implementations must add matching safety regressions.

`setup.sh` also installs the versioned `config/codex-tests.rules` as the project
`.codex/rules/tests.rules`, approving both categories. Codex must
trust the project configuration and be restarted after the rule is installed.
Linux Polkit authentication still applies. This grants trust to future test
code and its imports in this checkout; it is not a sandbox for malicious tests.
The installed dispatcher changes only when setup reinstalls it. It activates
on its next invocation (`none`), adds no service or Polkit policy, and is not
part of the product package. Run setup again if the checkout moves.

### Manual entry points

Before a host-integrated test that terminates processes, run its cleanup-safety
regressions in isolation. They must pass before the protected operation starts.
For the existing aggregate local/system commands, this cleanup-only selection
covers the current UI, nested-Shell, VM controller and persistent caller paths:

```sh
/usr/bin/python3 -B -m pytest \
  tests/unit/test_ui_cleanup_safety.py \
  tests/unit/test_child_preview_cleanup_safety.py \
  tests/unit/test_prepare_host_cleanup_safety.py \
  tests/unit/test_system_runner_cleanup_safety.py \
  tests/unit/test_system_caller_cleanup_safety.py \
  tests/unit/test_system_agent_cleanup_safety.py -q
```

For a focused test, select the safety modules for every cleanup implementation
it uses. New controllers must add their own ownership regressions. Future
`test-*` dispatch runs the applicable prerequisites automatically, including
for focused selections; today's commands do not all provide that orchestration.

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
