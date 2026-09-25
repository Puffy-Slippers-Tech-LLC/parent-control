# Repository approval tools and unattended execution

This is the maintained approval contract for the whole repository: research,
source and documentation edits, builds, tests, diagnostics, development setup,
VM maintenance and authorized publishing. Routine authorized work runs fully
unattended through existing grants and validated tools. The contract governs
development operations; product authorization remains in the
[system design](System-Design.md).

## Default workflow and rare exceptions

Carry authorized work through implementation and verification without repeated
permission requests. Reuse authorization already given in the session; routine
implementation choices, file names and tests within an established category do
not require separate approval.

Behavioral test failures follow the [regression failure contract](../tests/README.md#handling-test-failures):
report the potential regression and ask the developer to confirm intended
behavior before accepting a change or altering expectations, unless the specific
behavior change is already explicitly authorized. Unattended execution does not
authorize redefining expected product behavior to make tests pass. Mechanical
test defects may be fixed automatically while preserving the intended checks.

| Work | Unattended route |
| --- | --- |
| Repository reads and public research | Direct quoted reads under existing grants; `tools/read-only` for validated search, filters and fetches |
| Source and documentation edits | Native `apply_patch` within workspace permissions; `tools/read-only links` for Markdown |
| Builds and checks | Approved plain Make targets or validated `tools/run-tests`, `tools/run-unit-tests` and `tools/run-ui-tests` selections |
| Logs and system diagnostics | Ordinary readers where accessible; `tools/diagnose` and scoped artifact/export helpers where privileged access is needed |
| Setup refresh and VM maintenance | `./setup.sh` modes, `tools/prepare-baseline` and `tools/test-vm` within their existing grants and authorized scope |
| E2E prerequisites | `tools/cleanup-e2e` for recorded leftovers; `tools/prepare-appsnapshot [--overwrite true\|false]` for the current version snapshot through the pinned dispatcher and shared VM lease |
| Publication | Direct `tools/publish.py` once publication itself is authorized; see [publishing](#publishing) |

Invoke approved commands directly. Correct quoting and command shape before
interpreting a failure as missing authorization. When local sockets or ownership
metadata require execution outside the sandbox, use the existing scoped helper
grant. Do not add duplicate rules, broad shell/interpreter grants or permission
prompts to work around restrictive policy.

Human authorization is exceptional: initial administrator bootstrap, repair of
a denied installation from an administrator-authorized root session, an operation
outside the user's authorized scope, or a capability blocked by applicable policy.
An executable grant does not itself authorize a release, baseline replacement or
unrelated destructive action. Missing prerequisites or grants are blockers, not
invitations to bypass controls or retry authentication. Report the exact blocker
and required setup or scope decision; continue independent authorized work.

New recurring operations should use an existing validated route where possible.
If a new privileged capability is needed, maintain a scoped helper with argument
validation and regression coverage. Do not normalize per-command approvals.

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
dependencies and host policies. Explicit baseline preparation is
`tools/prepare-baseline`; see
[VM prerequisites](../tests/integration/Environment.md).
The tools-only refresh also fills missing `curl`, `ripgrep`, Python coverage
plugin and GTK 4 VTE viewer packages without requesting package upgrades; ordinary test commands
never install dependencies. Full setup includes these prerequisites too.

The [rules renderer](../tools/install_codex_rules.py) validates its required
launcher inventory, then discovers every regular executable under `tools/`
without following symlinks. The user preapproves direct project-tool execution;
setup renders one allow rule containing the exact `tools/`, `./tools/` and
checkout-absolute executable paths. This includes validated launcher actions and
argument orders. A new executable joins the grant at the next rules refresh;
removed or nonexecutable tools leave it. Codex matches literal argument tokens,
so a `tools/*` string is not a directory-wide grant. General shells/interpreters
and arbitrary privileged wrappers retain their restrictions. The tools' own
argument validation, task authorization and VM/Polkit guards still apply.
Simulated checkouts must copy that complete inventory too:
`test_rules_render_for_a_checkout_with_spaces` in the
[installation regressions](../tests/unit/test_dev_tool_installation.py)
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
The standalone app-snapshot route requires the current installed test dispatcher;
refresh it with `./setup.sh --test-tools-only` when adding these tools. It shares
the existing test-runner Polkit action, cleanup gate and fixed VM UUID, without
adding general snapshot or libvirt permissions.
There is no product package, service restart, reboot, or saved-data migration.
Graphical AppArmor policies are installed by full `./setup.sh` and refreshed by
`--test-tools-only`. Host package dependencies belong to full setup or
`--dependencies-only`. Codex setup also installs its maintained machine-wide
`pwd`, `git status`, `rg -n` and `sed -n` rules in `/etc/codex/rules/onpc-read-only.rules`, without
changing unrelated system/user rules. These reads cover any working directory
or repository; select a repository with the command tool's working directory.

## Publishing

Run `make publish` to invoke the single [publisher](../tools/publish.py).
It validates `docs/VersionHistory.md`, signs, pushes
the source and tags, uploads to Launchpad, and verifies binary publication.
Its supporting modules are under `tools/publishing/`; they are not separate
release commands.

Local publishing checks run through the aggregate's `tools/run-tests publish` category
and the same module in `make test-all`. They create a private unsigned source
snapshot, run source integrity and Lintian checks, and build/test it in clean
sbuild. They require no publisher credentials and never push or upload.

Manual execution on a configured host needs no approval or Polkit dialog.
When an assistant performs an authorized publication, direct `tools/publish.py`
uses the project-tool command grant. `make publish` still needs command approval
if platform policy requires it. Tool execution approval alone does not request
publication. The old preparation-only
launcher and its maintained allow rule have been removed.
See [unattended publishing](Publishing.md#unattended-operation-and-approvals).

No setup, privilege-policy change or general interpreter/shell allowance is
needed for this refactoring. Development activation is `none`: it changes no
installed services or saved data. The Debian activation helper moved to
`debian/package_activation.py`; its installed command and behavior are unchanged.

## Launcher inspection and workspace edits

Inspect validated launchers directly with their documented help and listing
commands. General interpreter and shell grants remain restricted.

After a rules refresh, restart the Codex process and resume the saved chat to
load the trusted project rules. Merely switching chats inside an existing
process is not a documented rule reload. Resuming restores the conversation;
it does not automatically reissue a command cancelled at an approval prompt.
Continue the task to issue that command again under the newly loaded rules.

For authorized workspace text edits, use native `apply_patch` with explicit
paths/context, subject to workspace write permissions. No shell-prefix grant is
needed. The reported `python3 -` heredoc edited a document, but allowing that
prefix also permits arbitrary imports, execution and writes; rules cannot
inspect Python semantics. Never add interpreter, shell or generic shell-patch
grants for document edits.

Use the existing document-check allowance, without per-file rules or refresh:

```sh
tools/read-only links 'docs/Approval-Tools.md' 'README.md' 'AGENTS.md'
tools/read-only words --after '## Ordered building-block catalogue' 'docs/TestAutomation/E2E-Building-Blocks.md'
```

| Check | Contract |
| --- | --- |
| `links` | Checks inline Markdown link/image destination files relative to each document. Handles plain, angle-wrapped, balanced/escaped parentheses and optional titles. Ignores code spans/fences, URLs and fragment-only links; does not fetch or validate anchors, reference-style or HTML links. |
| `words` | Counts whitespace-separated source words in one UTF-8 file, optionally between exact `--after`/`--before` markers. Each marker must occur once in the selected text; missing/ambiguous markers fail. Without `--before`, counts to EOF. |

Both accept regular files up to 8 MiB, refuse final symlinks/special files, and
expose no code, command, output-file or interpreter options. Link-check exits:
0 success, 1 missing targets, 2 invalid request/read failure. Failure diagnostics
give document argument number/line without copying prose or destinations.

The [rule matching contract](https://learn.chatgpt.com/docs/agent-configuration/rules#understand-rule-fields)
matches literal argument prefixes; the strictest decision wins.
`match`/`not_match` examples test rules, not runtime arguments.

## Category coverage and future additions

Setup authorization is separate from runtime test authorization. The installed
`/usr/local/libexec/onpc-setup` accepts exactly one of `dependencies`,
`codex-rules`, `test-tools`, `graphical-policy`, `ppa-build-tools` or `prepare-baseline`, with no extra
paths or arguments. Its
dedicated Polkit action defaults to denial and grants only active local members
of `sudo`. `setup.sh` and `tools/prepare-baseline` check this authorization without
requesting interaction before invoking the helper, and never fall back to generic
`pkexec` on denial. The public baseline-replacement entry is `tools/prepare-baseline`.
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

Use `tools/run-tests --help` for usage and the `all` composition, or
`tools/run-tests --list` for the ordered granular JSON inventory with explicit
argument arrays. This partition is shared by `all` and `tools/fix-tests`;
composites, instrumentation and diagnostics are listed separately in `--help`.
Paths are relative to
the checkout. Quote globs and parametrized pytest IDs so Codex sees a literal
argument; the launcher expands file patterns without a shell.

Choose validation scope from the change and its regression risk, independently
of scheduling. Prefer `tools/run-tests ui` for UI-only coverage,
`tools/run-tests unit` for unit-only coverage, and category/file/case selections
for the required subset. Use the launcher's existing parallelism where that
selection supports it. Never substitute `host` or `all` merely because the
selected suite is large or slow; additional suites and package builds need
their own validation justification. Direct unit/UI launchers remain suitable
for narrow iteration or diagnosis.

`tools/run-tests ui` reuses the aggregate's UI buckets, cleanup gate and scheduler
with up to four branches, without other host suites or package builds. File/case
selectors, `-k`, `-m` and scoped ignores retain the exact selected inventory.
Execution defaults to the host's 1800-second per-bucket timeout; an explicit
`--timeout` is preserved. `-x`/`--exitfirst` or positive `--maxfail` keeps one
serial invocation so its failure limit remains selection-wide. Inspection is
unchanged. No marker exclusions are added implicitly. Other categories stay
ordered. `tools/run-tests unit` uses the same four balanced unit buckets as
`host`, keeps module fixtures together and preserves exact selectors/options.
It adds no cleanup prerequisite inventory or other categories. Unknown modules
retain exclusive fallback; reviewed full application-fixture tests use artifact
resource admission and compatible overlap. New host modules require the
[parallelism review](../tests/README.md#host-test-parallelism-review); `-x` or
positive `--maxfail` keeps one serial invocation. Direct `tools/run-unit-tests`
remains serial for narrow iteration. See the
[scheduling contract](../tests/README.md#all-established-regressions).

Use complete categories (`host`, `system`, and `e2e`) only when their complete
coverage is justified; combine them once to share reports and package inputs.
Never start multiple launchers concurrently; the launcher owns scheduling and
the checkout activity lock.

| Existing or planned coverage | Stable command / extension pattern | Boundary |
| --- | --- | --- |
| Unit, property, contract, harness and cleanup regressions | `tools/run-tests unit` with optional quoted selectors | Only the justified unit scope; direct `tools/run-unit-tests` remains available for narrow checks |
| Private-D-Bus components | `tools/run-tests component 'tests/component/test_*.py' -q` | Only this category; cleanup prerequisites run first |
| GTK, parent, shared form, feedback and nested Shell | `tools/run-tests ui` with optional quoted selectors | Only the justified UI scope; direct `tools/run-ui-tests` remains available for narrow checks |
| Child Node tests | `tools/run-tests child-node 'tests/child/**/*.test.mjs'` | `.test.mjs` and `.test.js`; defaults discover both |
| Child GJS adapters | `tools/run-tests child-gjs 'tests/child/**/*_test.js'` | Fixed GJS runtime; new private coverage directory |
| Shell/GJS static checks | `tools/run-tests static` or `static shell` / `static gjs` | Fixed maintained checkers |
| Graphical backend readiness | `tools/run-tests backend` | Read-only package/API check; no privilege or VM operation |
| Requirement mapping | `tools/run-tests traceability stage` / `final` | Fixed verifier and its two modes |
| Python branch coverage | `tools/run-tests coverage` | Unit and private-bus layers only; new private report directory |
| Current aggregates | `tools/run-tests check` / `component-all` | Fixed Makefile/target; no Make options, extra targets or variable injection |
| App fixtures | `tools/run-tests fixtures build` / `verify /tmp/onpc-...` | Fixed builder; builds generate an empty private output directory |
| Package/fixture artifacts and reproducibility | `tools/run-tests artifacts build` / `verify /tmp/onpc-...` / `compare /tmp/onpc-first /tmp/onpc-second` | Fixed builder; explicit existing project artifact inputs |
| Reusable package/fixture preparation | `tools/run-tests artifacts prepare` | Content-qualified reuse or a fresh build; new private output registered in bounded run retention. No VM or installed product changes. |
| Named qualification inputs | `tools/run-tests artifacts build --output '/REPO/output/test-runs/host/allocations/onpc-parent-setup-input'` | Replace `/REPO` with this checkout's absolute path. Same unprivileged builder and retention; a new direct managed `onpc-*` allocation only, exclusive creation, no overwrite. `integration check_e2e_toggle` prepares this input automatically when absent. |
| Privileged harness/graphical checks | `tools/run-tests integration check_future_feature` | Direct `tests/integration/check_[a-z][a-z0-9_]*.py`; no script options |
| Installed identity, authorization, enforcement, time, activation, migration, removal and reinstall | `tools/run-tests system --artifacts /tmp/onpc-... --area authorization --test 'case[param]'` | Existing guarded VM controller; future registered areas/cases need no new rule |
| Graphical journeys and harness scenarios | `tools/run-tests e2e` / `tools/run-tests e2e --id 1,3,4` / `tools/run-tests e2e --list` | Defaults to every runnable E2E case, reporting pending exclusions; no other test categories are dispatched. Missing artifacts are built automatically; `--artifacts '/tmp/onpc-...'` reuses verified inputs. Explicit pending/invalid IDs refuse before privilege checks. Guarded cleanup-safety prerequisites remain mandatory. See [commands and prerequisites](../tests/e2e/README.md#run-e2e-scenarios). |
| Asset-transfer runner qualification | `tools/run-tests e2e --qualify-transfer --artifacts /tmp/onpc-...` | Guarded diagnostic attempt with isolated safety prerequisites; no scenario/list selector or product installation; pending customer dispatch stays closed |
| Authenticated installation qualification | `tools/run-tests e2e --qualify-install --artifacts /tmp/onpc-...` | Fixed package installation through fixture-authenticated serial input; same guarded lease, private capture and safety prerequisites. No scenario/list selector; E2E-002 remains pending until its complete reboot/readiness journey passes |
| Established regressions | `make test-all` / `tools/run-tests all` / `tools/run-tests` | All established suites and ready E2E variants, automatic discovery, streaming report, owned cancellation; no selectors. No arguments starts `all` when idle; an active or unread session still attaches. |
| Scripted test repair | `tools/fix-tests [CATEGORY ...] [--model MODEL] [--effort high]` / `tools/fix-tests --stop` | Granular pass then complete regression retries by default; explicit categories expand to leaves and restrict repair and verification to that scope; detached scripting owner, catalog-selected Sol classifier and optional strongest-model app review per failure in fresh ephemeral sessions, existing sandbox/rules and test-runner cleanup; no automatic setup or authority expansion |
| Scripted E2E implementation | `tools/write-e2e [--sessions N] [--tasks N]` / `tools/write-e2e --stop` | Fresh Astra Low implementation and Astra High live/repair sessions; a parameterless new run defaults to 5 sessions and 1 completed task, while a new run with `--tasks` alone retains unlimited sessions; stop at either limit; plain invocation attaches unchanged, explicit live limits are signed adjustments applied at session boundaries (minimum zero; unlimited sessions become sessions already started plus N); safe stop at the next session boundary, Ctrl+C owned cancellation; staging of explicit paths and task-session worktree changes without commits, excluding prior work and output artifacts; existing grants and guarded test cleanup |
| Complete host category | `tools/run-tests host [--continue-on-errors]` | All host work, including publishing, two fresh builds and comparison, in the aggregate's four branches; no VM discovery, authorization or execution |
| Combined complete categories | `tools/run-tests host system e2e` | Equals `all`; any subset/order is accepted, scheduled host first, then sequential system and E2E; one report and shared package inputs; VM-only selections build their required input automatically |
| Host compatibility alias | `tools/run-tests host-builds [--serial-builds] [--continue-on-errors]` | Same scope as `host`; `--serial-builds` retains publishing/builds after the host join for a scheduling comparison |
| Local publishing checks | `tools/run-tests publish` | Shared source/sbuild/Lintian module included in `test-all` and `test-all-verify`; no selectors or publication |
| Future fast suite | `tools/run-tests fast --component broker --type contract` | Fixed `test-fast` target; refuses while unfinished |

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

The complete `host`, `system`, `e2e` selections and their combinations, plus
the `all`, `all-verify` and `host-builds` aliases, stop on the first
reported test failure by default, using the Ctrl+C cooperative shutdown path:
owned children finish cleanup, evidence is finalized, and the failure investigation
prompt is printed. Add the valueless `--continue-on-errors` flag to continue
independent tests after failures. Cleanup, infrastructure and prerequisite safety
refusals still apply. Reattachment preserves the original flags. `host-builds` also
accepts `--serial-builds` alongside this flag.
The leading `tools/run-tests --stop-on-error CATEGORY` option applies this
policy to selected categories while preserving their qualified parallelism.
The repair loop uses it, and reads the generated `failure.json` handoff after
cleanup. It never treats an attached predecessor's result as a new category run.
Its [`tests/README.md` contract](../tests/README.md#scripted-repair-loop) describes
detachment, stop/restart behavior and agent isolation. Development activation is
`none`: these are checkout tools; no product installation, service restart or
saved-data migration is involved. The new executable joins the normal tools
grant on a future rules refresh; no broad shell/interpreter permission is added.

Every `tools/run-tests` category runs in a terminal-independent session. Closing
the terminal detaches; Ctrl+C requests owned cancellation and cleanup. While a
session is active or its successful final result remains unread, a new execution invocation warns
and attaches to it before interpreting arguments. All new arguments, including
listing, different categories and invalid selections, are ignored. After
the result is delivered, the next invocation validates and starts fresh work.
An explicit selection can replace an idle failed/incomplete session immediately,
preserving its output and reconciling residual state before starting tests.
An invocation without arguments still replays its unread result. When idle, no
arguments starts the `all` aggregate. `--help` and `-h` always print usage
immediately, before activity/session locks or attachment, without consuming an
unread result.

Internal workers inherit the verified checkout activity lock and execute their
assigned work without reattaching to their own session. Older runs without
session metadata still refuse competing launches through that lock.
Host-only selections use a separate activity lock, reconnect namespace and
retention journal, so
`tools/prepare-appsnapshot` can run alongside `tools/run-tests ui` or other
host-only tests. Selections containing system, E2E or integration work retain
the VM-side checkout lock and reconnect namespace; the privileged
cross-controller VM lease remains authoritative. A host run and a VM run can
therefore proceed and be reattached independently. Existing processes keep
their original locks until they exit.

Bulk output, scratch, reconnect state and retained exports use gitignored,
disk-backed `output/test-runs/`, with separate host and privileged ownership.
Legacy `/tmp/onpc-*` paths remain readable inputs, not new bulk output targets.
The [storage contract](../tests/README.md#aggregate-output-retention) defines
three-run/4-GiB per-journal rotation, owner-locked scratch reclamation, short
runtime-socket exceptions and explicit identity-audited legacy migration through
`tools/run-tests integration check_storage_migration`.

When starting a new run, system and E2E listings run as the ordinary user without safety tests, privilege
or VM mutation. `fast --list` forwards `LIST=1` once its target exists. `all`
accepts no narrowing arguments. Reserved entry points do not claim that the
corresponding suite is implemented or passing. Future aggregate work must reuse these routes
and the existing inventory/lease, including internally invoking the validated
system/E2E dispatcher. It must not introduce unrestricted Make arguments or a
second suite inventory. Future E2E execution accepts `--artifacts` and
`--scenario` and must implement the same guarded ownership and evidence contract.

Pytest options are intentionally bounded: quiet/verbose, exit-first, capture,
collection, warnings, `-k`, `-m`, maxfail, durations and traceback style. A scoped
`--ignore=tests/<category>/...` accepts validated file/directory patterns.
Configuration, plugins, arbitrary output paths and response files are refused.
Interpreter/plugin/loader/compiler/Make environment overrides are removed.
Coverage and build outputs use the shared disk-backed storage helpers; follow
the [test storage mandate](Mandates/Test-Storage-Mandate.md) for allocation and
the [artifact access contract](../tests/README.md#prompt-free-test-artifact-access)
for reading retained output.

Host-integrated categories run all `test_*cleanup_safety.py` and
`test_graphical_lease.py` in isolation before the protected operation. The
aggregate's UI, component and fixture-runtime workers may reuse its passing
gate only through the inherited checkout activity lock. Checkout edits do not
expire this passing gate. Fresh invocations clear the temporary record;
standalone commands still require prerequisites, and invalid records refuse.
The maintained cleanup coordinator can separately reuse a content-qualified
passing result across invocations; see
[startup preparation](../tests/e2e/README.md#reusable-startup-preparation).
Publishing, artifact and VM gates do not use the inherited host gate. The
privileged dispatcher obtains its qualification as the caller, then starts the
selected controller as root. Live VM authorization and ownership checks always
run. A failed prerequisite prevents the operation. Tests that
introduce another cleanup implementation must add its corresponding regression.
Collection/listing does not run cleanup or claim passing test coverage.

## The one test VM

All VM consumers inherit the [VM observation mandate](Mandates/VM-Mandate.MD#vm-observation-mandate).
`tools/watchvm` observes the shared lease and guarded command transport during
E2E, installed tests, qualifications, snapshot preparation and maintenance.
Publish nonsecret intent through `watch_activity.operation` or `observed` before
work starts; keep it visible through blocking work and restore enclosing intent
after nested work. Reuse this infrastructure for new routes. Independent capture,
SSH transcript or footer implementations are outside the contract. Viewing is
read-only and may attach or detach at any time without controlling VM activity.

`tools/test-vm` has no domain, URI, disk, XML, snapshot-name or arbitrary-command
argument. It uses `qemu:///system`, the name in
[config/test-vm.json](../config/test-vm.json), and the UUID pinned
from that name's root-private finalized baseline provenance during setup. A missing baseline
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
`tools/run-tests` invokes `integration check_test_recovery` automatically for
idle unfinished VM-side retention or before a new VM category. Host-only runs
leave VM-side retention untouched and refuse unfinished records in their own
journal. `tools/cleanup-e2e` also reconciles that host journal under its activity
lock after VM recovery succeeds. This uses the same
identity-checked recovery, mandatory cleanup prerequisites and exclusive leases;
it archives recovery markers after validation and leaves evidence in normal
retention. It never signals an unrecorded process or bypasses a failed VM audit.

## System reads

Use ordinary unprivileged readers for accessible files. For privileged system
diagnostics use `tools/diagnose`:

```sh
tools/diagnose journal --unit 'oh-no-parent-control*' --since '1 hour ago' --lines 500
tools/diagnose journal --kernel --boot=-1
tools/diagnose systemctl show 'oh-no-parent-control*' --property=ActiveState
tools/diagnose systemctl status 'libvirtd.service'
tools/diagnose read '/etc/polkit-1/rules.d/50-onpc-test-runner.rules'
tools/diagnose tail '/var/log/oh-no-parent-control/broker/2026-09-17.events'
tools/diagnose processes
tools/diagnose applications 1001
```

Other fixed reads are `disks`, `mounts`, `memory`, `cpu`, `kernel`, `network`,
`sockets`, `packages` and `sessions`. Systemd operations are status, show, cat,
list-units, list-unit-files, is-active and is-enabled. Journal options only
select units, date bounds, boot, kernel, output format and line count. Commands
disable pagers/authentication requests and have a bounded execution timeout.
Raw source output is for local inspection; only redacted evidence is shared.

`applications UID` lists only immediate filenames, types, modes and sizes in
that account's `Applications` folder. It resolves an ordinary UID through NSS,
requires a direct home under `/home`, pins every directory without following
symlinks, and refuses more than 4096 entries. It reads no application contents,
does not recurse, and accepts no arbitrary private path. This supports local
diagnosis of omitted AppImage wildcard rules in private child homes. The helper
update activates on its next invocation after `./setup.sh --test-tools-only`
(`none`); it changes no product service, saved data or privilege grant.

`launcher UID DESKTOP_ID` reads only selected launch metadata from a single
desktop file in that account's `.local/share/applications`. It uses the same
home boundary, refuses path components in the filename, symlinks at every
level, hardlinks, special files and entries over 64 KiB. It returns the main
entry's `Type`, `Exec`, `TryExec`, `Path` and selected AppImage metadata, never
other sections or arbitrary file contents. This is a local diagnostic for
incorrect AppImage target discovery; it never executes the launcher.

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
tools/read-only search --fixed-strings 'cleanup' 'tests' 'tools'
tools/read-only search --path-glob 'tests/integration/fixture*' 'password|credential|parent2|child2' 'tests/fixtures'
tools/read-only files 'tests' 'tools'
tools/read-only slice 10 80 'tests/README.md'
tools/read-only sort 'input.txt'
tools/read-only unique 'input.txt'
tools/read-only gzip 'archive.log.gz'
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

Preflight **every** path operand. If any needs filename expansion, use the
helper with a quoted `--path-glob` per pattern and quoted literal paths:

```sh
tools/read-only search --path-glob 'tools/*baseline*' --path-glob 'tests/integration/baseline*' '^(def|class) |environment|provenance|accepted'
tools/read-only files --path-glob 'tests/unit/test_graphical*'
```

The helper expands ordinary `*`, `?` and brackets internally, without shell,
variable/tilde or recursive `**` expansion. Matched directories get normal
search traversal; literal paths stay literal. Any unmatched pattern fails the
whole request before execution, never falling back to the current directory.

Direct `rg -n` supports quoted regexes and literal paths, plus quoted
ripgrep-owned `--glob` filters anchored to the literal search root:

```sh
rg -n 'perl|subprocess.run|Test::More' --glob '/tests/unit/test_graphical*' --glob '/tests/unit/test_e2e*' '.'
rg -n '^(def|class) |environment|provenance|accepted' --glob '/tools/*baseline*' --glob '/tools/*baseline*/**' --glob '/tests/integration/baseline*' --glob '/tests/integration/baseline*/**' '.'
```

Here leading slashes anchor to the checkout root; `/**` includes matching
directories' contents. Normal hidden-file, ignore and symlink handling applies.
For different traversal needs, discover with `rg --files` and appropriate
options, then pass literal filenames.

Never pass filename patterns as `rg` path operands: unquoted patterns invoke
shell expansion; quoting makes them literal filenames, not glob filters.
The reported graphical/E2E and baseline searches triggered shell approval this
way. The direct `rg -n` allowance already covers regex/path variations; another
allow or rule refresh cannot authorize the enclosing arbitrary shell script.

Quote every read path, even without spaces or with package-version `~`:

```sh
tail -100 '/tmp/onpc-build/output/package_1.2+ppa1~ubuntu26.04.1_amd64.build'
rg -n -B 8 -A 18 'Fatal Python|Segmentation|Current thread|test_feedback' '/tmp/onpc-build/output/package_1.2+ppa1~ubuntu26.04.1_amd64.build'
```

Submit reads/searches directly using the command tool's working directory,
keeping each full filename on one line. No explicit Bash wrapper, substitution,
assignment, redirection or unquoted filename wildcard. Correct malformed requests
before execution. If an ordinary read gets the general-shell approval reason,
fix quoting/shape and retry the same operation under its existing grant.
Never add shell/duplicate rules or refresh unchanged rules; honor actual denials
and remaining sandbox restrictions.

Quoted `tail`/`rg` reads of the `onpc-ppa-check-hmbj287y` build log succeeded
without approval on 2026-09-12. That qualifies this form in that session, not all
parser versions/contexts. `codex execpolicy check` tests an argument vector,
not command-tool shell splitting: a raw Bash wrapper matches its shell rule
even when the tool could split it. Prefix tests prove neither parser behavior
nor automatic approval for unquoted wildcards. See the
[parser boundary](https://learn.chatgpt.com/docs/agent-configuration/rules#shell-wrappers-and-compound-commands).

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
