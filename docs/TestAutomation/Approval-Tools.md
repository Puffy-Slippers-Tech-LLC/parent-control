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
First install uses `./setup.sh --bootstrap-tools` and can require administrator
authentication to establish the grant. Repeated bootstrap and routine refreshes
reuse the dedicated `onpc-setup` helper without asking for authentication.
Repair of an existing denied installation requires running that setup mode from
an administrator-authorized root session; it never falls back after denial. For Codex-only
changes, use `./setup.sh --codex-rules-only`. Repeat setup after moving the
checkout or changing installed helpers; adding tests within a supported category
does not require new approvals. A clean machine uses full `./setup.sh` for
dependencies and host policies. Explicit baseline preparation is also routed
through the master: `./setup.sh --prepare-host`; see
[VM prerequisites](../../tests/integration/Environment.md).
The tools-only refresh also fills missing `curl`, `ripgrep` and Python coverage
plugin packages without requesting package upgrades; ordinary test commands
never install dependencies. Full setup includes these prerequisites too.

The [rules renderer](../../tools/install_codex_rules.py) validates its entire
fixed launcher inventory before rendering.
Simulated checkouts must copy that complete inventory too:
`test_rules_render_for_a_checkout_with_spaces` in the
[installation regressions](../../tests/unit/test_dev_tool_installation.py)
covers this. A missing fixture launcher is a test-fixture failure, not a reason
to weaken rendering validation or refresh host permissions.

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
`pwd`, `git status`, `rg -n` and `sed -n` rules in `/etc/codex/rules/onpc-read-only.rules`, without
changing unrelated system/user rules. These reads cover any working directory
or repository; select a repository with the command tool's working directory.

## Publishing

Run `make publish` to invoke the single [publisher](../../tools/publish.py).
It validates `docs/VersionHistory.md`, signs, tests in clean local sbuild, pushes
the source and tags, uploads to Launchpad, and verifies binary publication.
Its supporting modules are under `tools/publishing/`; they are not separate
release commands.

Manual execution on a configured host needs no approval or Polkit dialog.
When an assistant performs an authorized publication, approve the whole
`make publish` process outside the sandbox at launch if platform policy requires
it. Local test permissions do not grant publication. The old preparation-only
launcher and its maintained allow rule have been removed.
See [unattended publishing](../Publishing.md#unattended-operation-and-approvals).

No setup, privilege-policy change or general interpreter/shell allowance is
needed for this refactoring. Development activation is `none`: it changes no
installed services or saved data. The Debian activation helper moved to
`debian/package_activation.py`; its installed command and behavior are unchanged.

## Launcher inspection and workspace edits

Use the executable checkout entry point for slice-launcher inspection:

```sh
tools/codex_slices.py --help
tools/codex_slices.py status
```

The maintained rule covers `--help`, `-h` and `status`, with `tools/`, `./tools/`
and the rendered absolute checkout path. Python runs in isolated mode without
bytecode writes. Help exits during argument parsing; status reads the fixed
saved state without starting a worker or changing it. Starting, stopping or
reconciling unattended work still needs authorization for that work. These
development-only changes activate on invocation (`none`); rules load after
`./setup.sh --codex-rules-only` and a Codex restart.

`python3 tools/codex_slices.py --help` matches the general interpreter prompt.
Adding a longer allow cannot override that prompt. Nor does `--help` make an
arbitrary script safe to execute. Keep the interpreter restriction and use the
reviewed executable route. Additional inspected tools need their own reviewed
argument boundary before joining maintained allowances.

For authorized workspace text edits, use Codex's native `apply_patch` tool with
explicit paths and enough context to identify the intended replacement. This
covers changing filenames, headings, dates and replacement text in task handoffs
and evidence documents without executing an inline Python program. It stays
subject to workspace write permissions and needs no shell-prefix allowance.
The reported `python3 -` heredoc rewrote a document, but an allowance for that
prefix would also accept arbitrary imports, process execution and writes outside
the intended document. Prefix rules cannot inspect Python semantics. Do not add
a Python, shell or generic shell-patch allowance for this operation.

The existing `tools/read-only` allowance also covers local document checks:

```sh
tools/read-only links docs/TestAutomation/Continuation.md docs/TestAutomation/Task-19.md docs/TestAutomation/Evidence/19B-Ordered-Recorder-20260908.md tests/e2e/README.md
tools/read-only words --after '### Task 19B continuation — 2026-09-08' docs/TestAutomation/Task-19.md
```

`links` checks inline Markdown link/image destination files relative to each
document, ignoring code spans/fences, URLs and fragment-only links. It accepts
plain, angle-wrapped and balanced/escaped-parenthesis destinations and optional
titles. It does not fetch URLs or validate anchors, reference-style links or
HTML links. Exit status is 0 for no missing targets, 1 for missing targets and
2 for an invalid request/read failure. Failures report the document's argument
number and line, without copying source prose or destinations into diagnostics.

`words` counts whitespace-separated source words in one UTF-8 file, optionally
after/before exact text markers. Each marker must appear exactly once in the
selected text; absent or ambiguous markers fail. Without `--before`, counting
continues to the end of the file, as in the reported Python handoff check. Both
checks accept regular files up to 8 MiB, refuse final symlinks and special files,
and expose no code, command, output-file or interpreter options. Filenames and
markers can vary under the same existing helper rule; no per-document approval
or rule refresh is needed for these added operations.

These boundaries follow the [official rule matching contract](https://learn.chatgpt.com/docs/agent-configuration/rules#understand-rule-fields):
patterns match literal argument prefixes, the strictest matching decision wins,
and `match`/`not_match` examples test a rule rather than validate runtime arguments.

## Category coverage and future additions

Setup authorization is separate from runtime test authorization. The installed
`/usr/local/libexec/onpc-setup` accepts exactly one of `dependencies`,
`codex-rules`, `test-tools`, `graphical-policy`, `ppa-build-tools` or `prepare-host`, with no extra
paths or arguments. Its
dedicated Polkit action defaults to denial and grants only active local members
of `sudo`. `setup.sh` checks this authorization without requesting interaction
before invoking the helper, and never falls back to generic `pkexec` on denial.
The dispatcher uses fixed modules from its pinned trusted checkout and a clean
environment; trust includes edits to that checkout's setup code. The dependency
operation runs only the fixed host-package module with noninteractive package
configuration. Checkout Git settings and the UI virtual environment run afterward
as the invoking user, outside the privileged dispatcher. Full clean-machine
setup establishes authorization before dependencies. Bootstrap authenticates
only when the helper is absent, reuses an existing grant, and stops on denial or
an unsafe existing helper. These
development-only changes activate on invocation (`none`) and change no product
data. Codex restarts do not change Polkit authentication policy.

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
| Graphical journeys, harness qualification, variants and fault/recovery scenarios | `tools/run-tests e2e --list --scenario E2E-001` / `tools/run-tests e2e --artifacts /tmp/onpc-... --scenario E2E-001` | Host-safe inventory preflight; invalid/pending execution refuses before privilege checks. Ready callbacks use the accepted guarded controller; E2E-001 supersedes E2E-034 and adds ordered GDM-return evidence; [19B's three public qualifications are accepted](Evidence/19B-Acceptance-20260908.md). Other 156 variants remain pending |
| Asset-transfer runner qualification | `tools/run-tests e2e --qualify-transfer --artifacts /tmp/onpc-...` | Guarded diagnostic attempt with isolated safety prerequisites; no scenario/list selector or product installation; pending customer dispatch stays closed |
| Authenticated installation qualification | `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-...` | Fixed package installation through fixture-authenticated serial input; same guarded lease, private capture and safety prerequisites. No scenario/list selector; E2E-002 remains pending until its complete reboot/readiness journey passes |
| Established regressions | `make test-all` / `tools/run-tests all` | All established suites and ready E2E variants, automatic discovery, streaming report, owned cancellation; no selectors |
| Future fast suite (Task 28A) | `tools/run-tests fast --component broker --type contract` | Fixed `test-fast` target; refuses while unfinished |

Routine `make check`, `make build`, `make check-release-version`, `make check-unit`,
`make check-component`, `make check-test-fixtures`, `make check-child-node`,
`make check-child-gjs`, `make check-child-shell`, `make check-shell`,
`make check-gjs` and `make check-static` also have maintained auto-approval rules
for `make` and `/usr/bin/make`. Run the plain target from this trusted checkout;
use the validated launchers above for selections/options. These are prefix
grants: they trust the Makefile, environment and trailing arguments, and cannot
enforce an exact argument count. No generic Make or shell allowance is installed.
Direct `make check-system`, `make check-e2e`, installation/removal and host/guest setup targets
retain prompts; use their validated routes and applicable authorization.

The former blanket `make` prompt overrode even a saved `make check` allow,
because the strictest matching rule wins. Do not restore that blanket prompt.
Codex splits a simple `/bin/bash -lc 'make check'` invocation and evaluates the
inner command, so it needs no shell allowance. Complex scripts retain the shell
prompt. After changing rules, run `./setup.sh --codex-rules-only` and restart
Codex with this checkout trusted. Setup maintains these target grants for clean
machines without changing personal user rules.

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
tools/read-only search --path-glob 'tests/integration/fixture*' 'password|credential|parent2|child2' tests/fixtures
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
read-only web requests remain authorized. The existing global `curl -fsSL`
allowance remains effective for direct public reads with a quoted literal URL:
`curl -fsSL 'https://example.com/path?query=value'`. Setup preserves that personal
rule without adding a duplicate or broader allowance. A blanket project `curl`
prompt previously overrode it even when the URL was correctly quoted; keep that
override removed. Refresh changed project rules through
`./setup.sh --codex-rules-only`, then restart Codex to load them.

Ordinary `rg -n` and `sed -n` reads are explicitly allowed machine-wide across
all paths. Project prompt rules must not blanket-match `rg` or `sed`, since
that overrides the global allow. Prefix rules do not validate trailing options;
use these direct allowances, including `curl -fsSL`, only for trusted reads and
the validated reader for untrusted arguments. The curl prefix can also match
trailing upload, custom-request or output options; the allowance does not
authorize those operations. `sort`, `uniq`, `gzip` and `wget` retain their project
prompt overrides. Use quoted ripgrep `--glob '*pattern*'` options instead of
unquoted shell wildcards: Codex can classify shell expansion as an unsplit shell
invocation, which the direct executable rule does not cover. Never grant a
generic shell to solve that parsing limitation.

### Ripgrep searches without shell expansion

Default to `tools/read-only search --path-glob 'path/prefix*' 'regex' literal/path`
when path operands need filename expansion. `search` and `files` accept repeated
`--path-glob` options and expand them inside the unprivileged helper, keeping
the command visible to the existing approval prefix. Patterns use ordinary
filename globbing (`*`, `?`, brackets), without shell evaluation, variable/tilde
expansion, or recursive `**` expansion. A matched directory is passed to the
search tool for its normal traversal. An unmatched pattern fails the whole
request before execution; it never falls back to searching the current directory.
Literal paths remain literal. Keep every pattern quoted. No setup refresh or
Codex restart is needed for this checkout helper change.

For the reported graphical/E2E unit-test search, use this direct command from
the checkout:

```sh
rg -n 'perl|subprocess.run|Test::More' --glob '/tests/unit/test_graphical*' --glob '/tests/unit/test_e2e*' .
```

The unquoted paths `tests/unit/test_graphical* tests/unit/test_e2e*` caused the
shell-level approval request. These quoted filters select matching files
directly under `tests/unit`; the literal `.` keeps their anchors relative to
the checkout. Pass the command directly to the execution tool without adding
`bash -lc`. The installed allowance already covers it; no refresh is required.

The installed `rg -n` prefix already allows every direct line-numbered search,
independent of regex and paths. A command such as
`rg -n '^(def|class) |environment|provenance|accepted' tools/*baseline* tests/integration/baseline*`
contains shell filename expansion. Codex therefore checks the enclosing
`/bin/bash -lc <script>` against the shell prompt rule, rather than checking
`rg -n`. Another ripgrep allow or a rules refresh cannot change that decision.
Prefix rules match literal argument tokens; they cannot express an exception
for arbitrary shell scripts whose text starts with `rg -n`.

Generate the search using quoted ripgrep globs and a literal root instead:

```sh
rg -n '^(def|class) |environment|provenance|accepted' --glob '/tools/*baseline*' --glob '/tools/*baseline*/**' --glob '/tests/integration/baseline*' --glob '/tests/integration/baseline*/**' .
```

Run this from the checkout using the command tool's working directory. The
leading slashes anchor filters to that search root; the `/**` filters include
contents of matching directories. This keeps unrelated nested baseline files
and other directories out of the search. Ripgrep's normal hidden-file, ignore
and symlink handling still applies when walking `.`. If explicitly selected
files need different traversal behavior, discover them with `rg --files` using
the appropriate options and pass literal filenames instead. Quoting a wildcard
path alone does not expand it: ripgrep treats `'tools/*baseline*'` as a literal
filename.

Correct this command form before requesting execution. Keep regexes and glob
values quoted, avoid shell substitutions/assignments/redirections, and do not
request a generic Bash grant. No policy change or restart is needed to use this
form with the already-installed direct search allowance.

`codex execpolicy check` tests the supplied argument vector; it does not exercise
the command tool's shell splitting. Passing a raw Bash wrapper to that checker
will match the shell rule even when a command tool could split its script.
Rule-prefix tests alone must not be reported as proof of shell parsing or of
automatic approval for unquoted wildcards. See the
[official rules documentation](https://learn.chatgpt.com/docs/agent-configuration/rules#shell-wrappers-and-compound-commands)
for the parser boundary.

## Approval limits and review findings

The earlier unit launcher validated paths; the UI launcher forwarded arbitrary
pytest arguments. Direct pytest rules likewise accepted external tests/plugins.
General privileged readers still caused Polkit dialogs despite Codex approval.
Saved global `virsh`, journal, filter/fetch and interpreter approvals could authorize
operations beyond their descriptions. These paths are replaced for routine work
by the validated helpers; project `prompt` overrides cover the relevant broad
global families without editing personal global rules. A prefix checks initial
arguments only, so adding an apparently safe subcommand is insufficient when
trailing options can execute code. The explicitly authorized routine Make target
prefixes and the existing `curl -fsSL` grant accept this limitation; they are not
argument-confined helpers.

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
