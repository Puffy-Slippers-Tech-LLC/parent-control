# Test and diagnostic approval tools

This is the maintained approval contract for current tests and the remaining
[test roadmap](../Test-Automation.md). It changes development tooling, not the
product's authorization or the roadmap's acceptance criteria. The task-session
model confirmation procedure applies when continuing a roadmap task, not to
routine approved commands.

## One-time setup

Run `./setup.sh --test-tools-only`, then restart Codex with this checkout trusted.
Setup installs root-owned helpers and scoped Polkit rules, pins the finalized
test baseline's VM UUID, and renders this checkout's absolute command prefixes.
Installation itself can require administrator authentication. For Codex-only
changes, use `./setup.sh --codex-rules-only`. Repeat setup after moving the
checkout or changing installed helpers; adding tests within a supported category
does not require new approvals. A clean machine uses full `./setup.sh` for
dependencies and host policies. Explicit baseline preparation is also routed
through the master: `./setup.sh --prepare-host`; see
[VM prerequisites](../../tests/integration/Environment.md).
The tools-only refresh also fills missing `curl`, `ripgrep` and Python coverage
plugin packages without requesting package upgrades; ordinary test commands
never install dependencies. Full setup includes these prerequisites too.

Dedicated Polkit actions bind these exact executable paths and default to `no`,
so missing authorization rules cannot trigger an authentication dialog. The
wrappers query their own process identity without action details, which Polkit
reserves for trusted callers. Polkit authorizes these programs for an active, local member of
Ubuntu's `sudo` group. Other callers receive a denial, without an authentication
dialog. The checkout launchers check that authorization noninteractively before
using `pkexec`, so a missing installation or unavailable grant fails with setup
guidance. They do not enable password caching, authorize general privileged
interpreters, or grant libvirt control to all domains.

The executable binding uses Polkit's documented
[`org.freedesktop.policykit.exec.path` action annotation](https://polkit.pages.freedesktop.org/polkit/pkexec.1.html),
with [default denial](https://polkit.pages.freedesktop.org/polkit/polkit.8.html)
and the scoped local-administrator rules applied separately.

Use Codex's ordinary escalation mechanism with the loaded helper prefix when
local sockets, system D-Bus or root-owned metadata require execution outside its
sandbox. Sandboxed owner remapping can look like an invalid installation; verify
that context before reinstalling or interpreting it as a host-policy denial.

Development activation is `none`: installed helpers change on their next
invocation, Polkit watches its rule directory, and Codex loads rules on restart.
There is no product package, service restart, reboot, or saved-data migration.
Graphical AppArmor policies are installed by full `./setup.sh` and refreshed by
`--test-tools-only`. Host package dependencies belong to full setup or
`--dependencies-only`. Codex setup also installs its maintained machine-wide
`pwd` and `git status` rules in `/etc/codex/rules/onpc-read-only.rules`, without
changing unrelated system/user rules. These reads cover any working directory
or repository; select a repository with the command tool's working directory.

## Category coverage and future additions

Use `tools/run-tests --list` for the category inventory. Paths are relative to
the checkout. Quote globs and parametrized pytest IDs so Codex sees a literal
argument; the launcher expands file patterns without a shell.

| Existing or planned coverage | Stable command / extension pattern | Boundary |
| --- | --- | --- |
| Unit, property, contracts, harness and cleanup regressions | `tools/run-unit-tests 'tests/unit/test_*.py' -q` or `tools/run-tests unit ...` | Only `tests/unit/**/test_*.py`; ordinary user |
| Private-D-Bus components | `tools/run-tests component 'tests/component/test_*.py' -q` | Only this category; cleanup prerequisites run first |
| GTK, parent, shared form, feedback and nested Shell | `tools/run-ui-tests --timeout 360s 'tests/ui/test_*.py' -q` | Only `tests/ui`; fixed venv, timeout and automatic safety prerequisites |
| Child Node tests | `tools/run-tests child-node 'tests/child/**/*.test.mjs'` | `.test.mjs` and `.test.js`; defaults discover both |
| Child GJS adapters | `tools/run-tests child-gjs 'tests/child/**/*_test.js'` | Fixed GJS runtime; new private coverage directory |
| Shell/GJS static checks | `tools/run-tests static` or `static shell` / `static gjs` | Fixed maintained checkers |
| Graphical backend readiness | `tools/run-tests backend` | Read-only package/API check; no privilege or VM operation |
| Requirement mapping | `tools/run-tests traceability stage` / `final` | Fixed verifier and its two modes |
| Python branch coverage | `tools/run-tests coverage` | Unit and private-bus layers only; new private report directory |
| Current aggregates | `tools/run-tests check` / `component-all` | Fixed Makefile/target; no Make options, extra targets or variable injection |
| App fixtures | `tools/run-tests fixtures build` / `verify /tmp/onpc-...` | Fixed builder; builds generate an empty private output directory |
| Package/fixture artifacts and reproducibility | `tools/run-tests artifacts build` / `verify /tmp/onpc-...` / `compare /tmp/onpc-first /tmp/onpc-second` | Fixed builder; explicit existing project artifact inputs |
| Privileged harness/graphical checks | `tools/run-tests integration check_future_feature` | Direct `tests/integration/check_[a-z][a-z0-9_]*.py`; no script options |
| Installed identity, authorization, enforcement, time, activation, migration, removal and reinstall | `tools/run-tests system --artifacts /tmp/onpc-... --area authorization --test 'case[param]'` | Existing guarded VM controller; future registered areas/cases need no new rule |
| Graphical customer journeys, variants and fault/recovery scenarios | `tools/run-tests e2e --list --scenario E2E-001` | Current inventory only; execution is reserved for the guarded `tests/e2e/runner.py` and refuses until implemented |
| Future fast suite and complete gate (Task 28A) | `tools/run-tests fast --component broker --type contract` / `tools/run-tests all` | Fixed `test-fast`/`test-all` targets; currently refuse because those targets are unfinished |

System and E2E listings run as the ordinary user without safety tests, privilege
or VM mutation. `fast --list` forwards `LIST=1` once its target exists. `all`
accepts no narrowing arguments. Reserved entry points do not claim that the
corresponding suite is implemented or passing. Task 28 must reuse these routes
and the existing inventory/lease, including internally invoking the validated
system/E2E dispatcher. It must not introduce unrestricted Make arguments or a
second suite inventory. Future E2E execution accepts `--artifacts` and
`--scenario` and must implement the same guarded ownership and evidence contract.

Pytest options are intentionally bounded: quiet/verbose, exit-first, capture,
collection, warnings, `-k`, `-m`, maxfail, durations and traceback style. A scoped
`--ignore=tests/<category>/...` accepts validated file/directory patterns.
Configuration, plugins, arbitrary output paths and response files are refused.
Interpreter/plugin/loader/compiler/Make environment overrides are removed.
Coverage and build outputs are generated under `/tmp/onpc-*`; keep future test
artifacts under the [shared storage roots](../../tests/README.md#prompt-free-test-artifact-access).

Host-integrated categories run all `test_*cleanup_safety.py` and
`test_graphical_lease.py` in isolation before the protected operation. The
privileged dispatcher runs these as the caller, then starts the selected
controller as root. A failed prerequisite prevents the operation. Tests that
introduce another cleanup implementation must add its corresponding regression.
Collection/listing does not run cleanup or claim passing test coverage.

## The one test VM

`tools/test-vm` has no domain, URI, disk, XML, snapshot-name or arbitrary-command
argument. It uses `qemu:///system`, the name `ubuntu26.04`, and the UUID pinned
from root-private finalized baseline provenance during setup. A missing baseline
disables this route until preparation and a tools refresh; it never selects a
replacement by name alone.

| Command | Effect |
| --- | --- |
| `tools/test-vm status` / `xml` | Inspect only the pinned guest using a read-only connection |
| `tools/test-vm start` | Acquire the shared lease, validate provenance/disks/snapshot, restore the outer baseline, remove host shares, record and boot an isolated maintenance attempt |
| `tools/test-vm reboot` | Request an ACPI reboot of that same recorded running instance; preserve guest state |
| `tools/test-vm send-key 28` | Send 1–16 numeric Linux keycodes (1–255) to that instance; no shell or host command |
| `tools/test-vm screenshot` | Capture the owned running guest to a new private `/tmp/onpc-vm-screen-*` artifact |
| `tools/test-vm stop` | Stop only that recorded maintenance instance, verify/restore the outer baseline and original domain configuration, leave it off |
| `tools/test-vm reset` | Restore the accepted outer baseline while idle, leaving the VM off |

Every mutation shares the runner's nonblocking exclusive lock. Reopened
maintenance operations require a matching root-private ownership record,
run/domain instance, original configuration, baseline digest and snapshot digest.
Other active controllers and replaced identities are refused. No new domain,
snapshot, clone, overlay, arbitrary XML, host-device attachment or general
guest/host shell is exposed. No reset occurs between reboot/input steps.
An already-running manually started VM is not adopted. Stop the maintenance
attempt before starting installed/E2E tests. A helper failure preserves its
record and evidence for diagnosis; unsupported interrupted phases require a
controller fix, not deletion of journals or a raw `virsh` workaround.

Use the installed/graphical runner for ordinary tests. These maintenance
commands do not produce complete customer-journey evidence. The existing
`integration check_graphical_recovery` remains the separate narrow recovery
route for an interrupted graphical runner, under its recorded identity checks.

## System reads

Use ordinary unprivileged readers for accessible files. For privileged system
diagnostics use `tools/diagnose`:

```sh
tools/diagnose journal --unit 'oh-no-parent-control*' --since '1 hour ago' --lines 500
tools/diagnose journal --kernel --boot=-1
tools/diagnose systemctl show 'oh-no-parent-control*' --property=ActiveState
tools/diagnose systemctl status libvirtd.service
tools/diagnose read /etc/polkit-1/rules.d/50-onpc-test-runner.rules
tools/diagnose tail /var/log/oh-no-parent-control/daemon/2026-09-07.log
tools/diagnose processes
```

Other fixed reads are `disks`, `mounts`, `memory`, `cpu`, `kernel`, `network`,
`sockets`, `packages` and `sessions`. Systemd operations are status, show, cat,
list-units, list-unit-files, is-active and is-enabled. Journal options only
select units, date bounds, boot, kernel, output format and line count. Commands
disable pagers/authentication requests and have a bounded execution timeout.
Raw source output is for local inspection; only redacted evidence is shared.

File read/tail/list/stat covers `/var/log`, systemd/Polkit/AppArmor/fapolicyd
configuration, installed systemd/Polkit definitions, dpkg package info, and
the fixed test baseline's controller-state directory. Every path component is
pinned without symlink traversal. Devices, FIFOs, hard links and unrelated
credential paths are refused. There are no source writes, deletions, journal
rotation/vacuum, service changes, arbitrary program arguments or shell escapes.
Test storage and exports continue through `onpc-test-artifacts`; graphical smoke
PNG exports continue through `onpc-export-screenshot`.

For common tools whose unrestricted options can write or execute commands, use
the unprivileged `tools/read-only` launcher:

```sh
tools/read-only search --fixed-strings 'cleanup' tests tools
tools/read-only files tests tools
tools/read-only slice 10 80 tests/README.md
tools/read-only sort input.txt
tools/read-only unique input.txt
tools/read-only gzip archive.log.gz
tools/read-only fetch 'https://example.com/path?query=value'
```

Filters accept input paths or stdin; none accepts an output path. Search accepts
regular expressions or fixed strings, without a preprocessor. HTTPS fetch uses
a fixed GET command with configuration disabled, HTTPS-only redirects and a
timeout; no upload, credentials, output file or custom request options. Public
read-only web requests remain authorized. Raw `rg`, `sed`, `sort`, `uniq`,
`gzip`, `curl` and `wget` now have project prompt overrides for their broad
saved grants; sandboxed ordinary reads still work. Use these wrappers for
repeated escalated reads. Never fix shell expansion by granting a general shell
or passing an unquoted pattern.

## Approval limits and review findings

The earlier unit launcher validated paths; the UI launcher forwarded arbitrary
pytest arguments. Direct pytest rules likewise accepted external tests/plugins.
General privileged readers still caused Polkit dialogs despite Codex approval.
Saved global `virsh`, Make, journal, filter/fetch and interpreter approvals could authorize
operations beyond their descriptions. These paths are replaced for routine work
by the validated helpers; project `prompt` overrides cover the relevant broad
global families without editing personal global rules. A prefix checks initial
arguments only, so adding an apparently safe subcommand is insufficient when
trailing options or Make targets can execute code.

The safety boundary trusts this checkout, its maintained test code/imports,
configuration and installed dependencies. A filename pattern cannot prove that
a newly written test is harmless. In particular, privileged integration tests
remain trusted root code. Review changes to helpers, tests and rules before
running code from an untrusted branch. Ordinary tests, known operations and
new names within the documented contracts need no individual approval; new
privileged capabilities need validation and regression coverage in a maintained
helper, not a broad shell/interpreter grant.

Absolute guarantees of no prompt are not possible: missing setup, inactive or
remote callers, sandbox denials, organization-managed rules and runtime policy
changes can override local grants. The goal is repeatable noninteractive
execution within the installed, validated scope, with explicit refusal outside
it. Codex and Polkit are separate controls. See the
[official Codex rules documentation](https://learn.chatgpt.com/docs/agent-configuration/rules)
for prefix matching, shell parsing, trust, startup loading and the precedence of
restrictive rules.
