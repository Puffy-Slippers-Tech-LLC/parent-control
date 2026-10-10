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
| Setup refresh and VM maintenance | `./setup.sh` modes, `tools/prepare-vm` and `tools/test-vm` within their existing grants and authorized scope |
| VM disaster recovery | `tools/backupvm` and `tools/restorevm` for registered selections and configured `backup_root`; fixed operations through the setup dispatcher, with shared leases and retained recovery evidence |
| E2E prerequisites | `tools/cleanup-e2e` for recorded leftovers; add `--discard-completed` only when discarding saved execution results is explicitly authorized, under [retention ownership](../tests/README.md#aggregate-output-retention); `tools/prepare-appsnapshot --vm NAME --y [--mode online\|offline] [--overwrite true\|false]` for the current version snapshot through the pinned dispatcher and shared VM lease |
| Publication | Direct `tools/publish.py` once publication itself is authorized; see [publishing](#publishing) |

Invoke approved commands directly. Correct quoting and command shape before
interpreting a failure as missing authorization. When local sockets or ownership
metadata require execution outside the sandbox, use the existing scoped helper
grant. Do not add duplicate rules, broad shell/interpreter grants or permission
prompts to work around restrictive policy.

Human authorization is exceptional: initial administrator bootstrap, repair of
a denied installation from an administrator-authorized root session, an operation
outside the user's authorized scope, or a capability blocked by applicable policy.
An executable grant does not itself authorize a release, manual baseline replacement or
unrelated destructive action. Auto-mode baseline refresh needed for authorized
development or testing has standing authorization under the
[VM mandate](Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
Missing generated test inputs and proven mechanical preparation defects must be
repaired automatically through maintained routes within existing authorization.
Prepare absent named qualification inputs with the artifact builder and resume
validation; choosing whether to build or restore them is an implementation detail,
not a developer question. Preserve existing inputs and all validation guards.
Prerequisites that cannot be repaired within that scope, and missing grants, are
blockers, not invitations to bypass controls or retry authentication. Report the
exact blocker and required external action; continue independent authorized work.

New recurring operations should use an existing validated route where possible.
If a new privileged capability is needed, maintain a scoped helper with argument
validation and regression coverage. Do not normalize per-command approvals.

Running translation-only `tools/sync-whatsnew`, including `--prepare`, requires
an explicit user request; its command grant and release-note edits do not
authorize automatic synchronization. Read-only `--check` remains allowed.
The launcher follows the
[localization workflow](SystemDesign/Localization.md#whats-new-translation-workflow):
latest numeric VersionHistory release and optional matching child TOML entry,
read-only coding-agent sessions, launcher-owned
translation asset writes and validation. It shares detached ownership and
retention; `--stop` cancels its owned session and `--check` is read-only. It grants
no infrastructure/source edits, setup, staging, installation or publication.

## One-time setup

Run `./setup.sh --test-tools-only`, then restart Codex with this checkout trusted.
Setup installs root-owned helpers and scoped Polkit rules, pins the finalized
test baseline's VM UUID, and renders portable project-relative command prefixes.
Installed helpers resolve the invoking repository root at execution time, rather
than retaining the installation checkout. Launchers select their repository root
and preserve it through `pkexec --keep-cwd`. Direct artifact and screenshot helper
invocations must likewise use `--keep-cwd` from the intended repository root.
The maintained Codex prefixes include that option before the exact helper path;
the allow selects host execution without granting general `pkexec` access.
If a reader reports `pkexec must be setuid root`, first compare its complete
argument prefix with the loaded rule. A command missing its allow can run inside
the sandbox even when other approved commands run on the host; inspecting
`/proc/self/status` with a separately allowed read does not inspect the failed
command's context. Do not infer a broken host installation from that error alone.
After a maintained rule correction, run `./setup.sh --codex-rules-only` and start
a fresh Codex process. Each launcher agent is a fresh process, so its next session
loads refreshed rules; an already-running agent keeps its original policy.
The embedded resolver checks repository markers, ownership, permissions and
symlinks before loading checkout code. It does not replace Polkit authorization.
First install uses `./setup.sh --bootstrap-tools` and can require administrator
authentication to establish the grant. Repeated bootstrap and routine refreshes
reuse the dedicated `onpc-setup` helper without asking for authentication.
Repair of an existing denied installation requires running that setup mode from
an administrator-authorized root session; it never falls back after denial. For Codex-only
changes, use `./setup.sh --codex-rules-only`. Repeat setup after moving the
checkout or changing installed helpers; adding tests within a supported category
does not require new approvals. A clean machine uses full `./setup.sh` for
dependencies and host policies. Full setup and `--dependencies-only` also prepare
the caller-owned Fedora 44 RPM build image. `--rpm-build-tools` installs only its
RPM/Podman host prerequisites and prepares that image; refresh an older installed
setup helper with `--test-tools-only` first. Builds never install prerequisites.
Explicit baseline preparation is
`tools/prepare-vm --vm NAME --mode auto|manual [--y]`; launcher/session
work includes `--y`, while manual work omits it to retain confirmation. See
[VM prerequisites](../tests/integration/Environment.md).
Reusable guest dependencies, fixed fixture apps/launchers and persistent harness
settings belong exclusively to this baseline route. Test runners and app-snapshot
preparation verify them and report missing or stale state; they never install or
repair them implicitly. Invoke authorized baseline refresh separately. Its finite
inventory must reconcile idempotently, preserve unrelated state and safely retry
owned partial work; see the [baseline mandate](Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
The tools-only refresh also fills missing `curl`, `ripgrep`, Python coverage
plugin and GTK 4 VTE viewer packages without requesting package upgrades; ordinary test commands
never install dependencies. Full setup includes these prerequisites too.
For an additional worktree on a configured host, `./setup.sh --ui-tests-only`
creates its checkout-local UI environment from the pinned requirements. This
unprivileged mode changes neither host package versions nor Git configuration;
missing system prerequisites still require the normal dependency setup route.

The [rules renderer](../tools/install_codex_rules.py) validates its required
launcher inventory, then discovers every regular executable under `tools/`
without following symlinks. The user preapproves direct project-tool execution;
setup renders one allow rule containing the exact `tools/` and `./tools/`
executable paths. Run these commands with the intended checkout root as the
working directory; the same rules then apply across worktrees and local
enlistments without embedding checkout locations. Installed system helpers keep
their fixed absolute paths. This includes validated launcher actions and
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
the existing test-runner Polkit action, owned recovery and fixed VM UUID, without
adding general snapshot or libvirt permissions.
Automation and agent sessions include `--y` for authorized preparation.
Manual work omits `--y` to confirm before preparation. Selection and rolling
concurrency follow the [VM mandate](Mandates/VM-Mandate.MD#authority-and-operation),
including lists, `all-enabled`, `all`, and the enabled default when `--vm` is
omitted. The flag preserves all authorization, lease, ownership and validation checks.
Online mode is the default and reuses fresh matching snapshots without building.
`--overwrite` defaults to `false` online and `true` offline; supplying the flag
without a value means `true`. Use `--mode offline` for shutdown/snapshot
preparation or `--overwrite true` for an authorized forced rebuild.
The verified baseline selects Ubuntu 26.04 DEB/APT or Fedora Workstation 44
RPM/DNF preparation. Fedora uses the maintained native/Mock/rootless container
builder and preserves enforcing SELinux during offline SSH bootstrap and installation.
Online mode leaves the restored running guest in the existing VM-maintenance ownership
journal. Its restore-only dispatch uses maintenance scratch rather than an
evidence-retention session, whose entry gate requires an idle VM. The shared
owned recovery and live VM ownership checks still apply. Offline mode
retains the previous shutdown/snapshot behavior. Mode mismatches and online
snapshots older than 24 hours force replacement. Explicit overwrite still rebuilds.
Standalone app preparation holds a named VM checkout activity lock, so different
VMs may prepare concurrently while the same VM and aggregate owners remain
excluded. A read-only snapshot probe sends unfinished attempts through shared
recovery before probing again. Healthy online maintenance resumes directly;
replacement recovers its exact recorded owner through the maintained stop path.
Failed SSH or clock readiness after a successful restore performs owned cleanup.
Tooling activation is `none` on the development host. Guest snapshot preparation
still installs the declared product package and performs the mode's required
restart; it supplies no customer-acceptance credit.
Graphical AppArmor policies are installed by full `./setup.sh` and refreshed by
`--test-tools-only`. Host package dependencies belong to full setup or
`--dependencies-only`. Codex setup also installs its maintained machine-wide
`pwd`, `git status`, `rg -n` and `sed -n` rules in `/etc/codex/rules/onpc-read-only.rules`, without
changing unrelated system/user rules. These reads cover any working directory
or repository; select a repository with the command tool's working directory.

## Publishing

Run `make publish` from the dedicated `releases/vX.Y` checkout to invoke the
single [publisher](../tools/publish.py).
It validates `docs/VersionHistory.md`, commits pending release-checkout changes,
signs, pushes
the source to that release branch and tags, uploads to Launchpad, and verifies
binary publication. It asks for confirmation of a development pause before
directly merging committed release changes into main, then automatically
cherry-picking and pushing release metadata to main. Its
checkout-local publishing lock does not participate in development/build/test
activity locking. After the highlighted main-update handoff, development
continues independently of publication monitoring.
Its supporting modules are under `tools/publishing/`; they are not separate
release commands.

Local publishing checks run through the aggregate's `tools/run-tests publish` category
and the same module in `make test-all VM=NAME`. They create a private unsigned source
snapshot, run source integrity and Lintian checks, and build/test it in clean
sbuild. They require no publisher credentials and never push or upload.

Manual execution on a configured host needs no administrator approval or
Polkit dialog; the publisher's explicit main-pause confirmation is required.
When an assistant performs an authorized publication, direct `tools/publish.py`
uses the project-tool command grant. `make publish` still needs command approval
if platform policy requires it. Tool execution approval alone does not request
publication.
See [unattended publishing](Publishing.md#unattended-operation-and-approvals).

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
needed. Interpreter prefixes also permit arbitrary imports, execution and writes;
rules cannot inspect script semantics. Never add interpreter, shell or generic shell-patch
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
`codex-rules`, `test-tools`, `graphical-policy`, `ppa-build-tools`, `rpm-build-tools`,
`replace-missing-baseline`, `prepare-vm`, `backupvm` or `restorevm`.
The disaster recovery operations accept only a registered `--vm` queue selector
(default `all`), never caller-supplied archive, domain XML or disk paths. They
use `backup_root` from the trusted registry and the existing setup authorization;
see [VM disaster recovery](../tests/integration/Environment.md#vm-disaster-recovery).
Only `prepare-vm`
requires the fixed arguments `--mode auto` or `--mode manual`, optionally
followed by `--y`; arbitrary paths
and other arguments are refused. Its
dedicated Polkit action defaults to denial and grants only active local members
of `sudo`. `setup.sh` and `tools/prepare-vm` check this authorization without
requesting interaction before invoking the helper, and never fall back to generic
`pkexec` on denial. The public baseline-replacement entry is
`tools/prepare-vm --vm NAME --mode auto|manual [--y]`; the
[VM mandate](Mandates/VM-Mandate.MD#vm-host-setup-and-baseline) owns mode
authorization, selector scope, warnings and preparation lifetime. Auto restores
the accepted baseline and updates the supported guest distribution; manual
prepares the current disk state. Both capture `onpc_baseline` after validation,
prepare the current online app snapshot through shared app-snapshot code, and
restore the baseline with the VM off. One exclusive VM lease covers all stages;
package building runs as the authenticated unprivileged caller.
The dispatcher uses fixed modules relative to the invoking repository root and a
clean environment; trust includes edits to that checkout's setup code. The dependency
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
argument arrays and a `host` or `vm` scope. The disjoint partition is
`host + vm = all`, with `vm = system + e2e`. This partition is shared by `all` and `tools/fix-tests`;
composites, instrumentation and diagnostics are listed separately in `--help`.
Paths are relative to
the checkout. Quote globs and parametrized pytest IDs so Codex sees a literal
argument; the launcher expands file patterns without a shell.

Select the lowest effective scope under the
[suite selection and scheduling contract](../tests/README.md#all-established-regressions).
It owns exact selectors, timeouts, failure limits, UI's `live_e2e` exclusion and
parallelism within each category. New host modules and resource changes also
need [parallelism review](../tests/README.md#host-test-parallelism-review).
Command authorization does not justify expanding a focused check to `host` or `all`.

In the command patterns below, `ARTIFACTS`, `FIRST` and `SECOND` mean the exact
paths returned by maintained builders; quote each substituted path. New output
uses [shared disk-backed storage](Mandates/Test-Storage-Mandate.md). Existing
validated legacy `/tmp/onpc-*` bundles remain accepted inputs, not output examples.

| Existing or planned coverage | Stable command / extension pattern | Boundary |
| --- | --- | --- |
| Unit, property, contract, harness and cleanup regressions | `tools/run-tests unit` with optional quoted selectors | Only the justified unit scope; direct `tools/run-unit-tests` remains available for narrow checks |
| Private-D-Bus components | `tools/run-tests component 'tests/component/test_*.py' -q` | Only this category; live ownership checks remain active |
| GTK, parent, shared form, feedback and nested Shell | `tools/run-tests ui` with optional quoted selectors | Only the justified UI scope; direct `tools/run-ui-tests` remains available for narrow checks |
| Child Node tests | `tools/run-tests child-node 'tests/child/**/*.test.mjs'` | `.test.mjs` and `.test.js`; defaults discover both |
| Child GJS adapters | `tools/run-tests child-gjs 'tests/child/**/*_test.js'` | Fixed GJS runtime; new private coverage directory |
| Shell/GJS static checks | `tools/run-tests static` or `static shell` / `static gjs` | Fixed maintained checkers |
| Graphical backend readiness | `tools/run-tests backend` | Read-only package/API check; no privilege or VM operation |
| Requirement mapping | `tools/run-tests traceability stage` / `final` | Fixed verifier and its two modes |
| Python branch coverage | `tools/run-tests coverage` | Unit and private-bus layers only; new private report directory |
| Current aggregates | `tools/run-tests check` / `component-all` | Fixed Makefile/target; no Make options, extra targets or variable injection |
| App fixtures | `tools/run-tests fixtures build` / `verify 'ARTIFACTS'` | Fixed builder; builds generate an empty private output directory |
| Package/fixture artifacts and reproducibility | `tools/run-tests artifacts build` / `verify 'ARTIFACTS'` / `compare 'FIRST' 'SECOND'` | Fixed builder; explicit existing project artifact inputs |
| Reusable package/fixture preparation | `tools/run-tests artifacts prepare` | Content-qualified reuse or a fresh build; new private output registered in bounded run retention. No VM or installed product changes. |
| Named qualification inputs | `tools/run-tests integration --vm NAME check_parent_setup` | Integration qualifications using `named_input()` automatically select current source-keyed inputs and prepare absent bundles before privileged dispatch. Same unprivileged builder and retention; exclusive creation, no overwrite. A legacy fixed-name bundle is never selected. Launcher regression coverage checks every consumer. |
| Privileged harness/graphical checks | `tools/run-tests integration --vm NAME check_future_feature` | Direct `tests/integration/check_[a-z][a-z0-9_]*.py`; no script options |
| Installed identity, authorization, enforcement, time, activation, migration, removal and reinstall | `tools/run-tests system --vm NAME --artifacts 'ARTIFACTS' --area authorization --test 'case[param]'` | Existing guarded VM controller; future registered areas/cases need no new rule |
| Graphical journeys and harness scenarios | `tools/run-tests e2e --vm NAME` / `tools/run-tests e2e --vm NAME --id 1,3,4` / `tools/run-tests e2e --vm NAME --list` | Defaults to every runnable E2E case, reporting pending exclusions; no other test categories are dispatched. Missing artifacts are built automatically; `--artifacts 'ARTIFACTS'` reuses verified inputs. Explicit pending/invalid IDs refuse before privilege checks. Serial owned recovery remains mandatory; no prerequisite test suite runs. See [commands and prerequisites](../tests/e2e/README.md#run-e2e-scenarios). |
| Asset-transfer runner qualification | `tools/run-tests e2e --vm NAME --qualify-transfer --artifacts 'ARTIFACTS'` | Guarded diagnostic attempt with live ownership checks; no scenario/list selector or product installation; pending customer dispatch stays closed |
| Authenticated installation qualification | `tools/run-tests e2e --vm NAME --qualify-install --artifacts 'ARTIFACTS'` | Fixed package installation through fixture-authenticated serial input; same guarded lease, private capture and owned recovery. No scenario/list selector; diagnostic qualification supplies no complete-scenario acceptance. Current bindings belong to the [scenario inventory](../tests/e2e/scenarios.json). |
| Established regressions | `make test-all VM=NAME` / `tools/run-tests all --vm NAME` / `tools/run-tests --vm NAME` | All established suites and ready E2E variants, automatic discovery, streaming report, owned cancellation; no selectors. With only `--vm NAME`, starts `all` when idle; [reconnection](../tests/README.md#aggregate-execution-and-reconnection) retains the original canonical selection. |
| Scripted test repair | `tools/fix-tests [--vm NAME] [CATEGORY ...] [--model MODEL] [--effort EFFORT] [--rounds X]` / `tools/fix-tests --vm NAME --stop` | Granular pass only by default; --rounds X adds X-1 verification rounds; explicit selectors remain fixed. The [repair policy](../tests/README.md#scripted-repair-loop) owns GPT-6.1 Sol Medium → High → xHigh → Max escalation, with Low → Medium → High → xHigh for unit failures (including mixed/aggregate runs), five sessions per case/VM including answered blockers, and bounded diagnostic changes handed to launcher-owned execution. Fresh serial Standard-speed sessions preserve stronger effort overrides; other models are refused and final-tier stalls may stop early. Different-case/preparation interruptions leave verification unknown. Existing sandbox/rules and owned cleanup apply; no automatic setup or authority expansion. |
| Scripted E2E implementation | `tools/write-e2e --vm NAME [--sessions N] [--tasks N]` / `tools/write-e2e --vm NAME --stop` | The [launcher policy](../tests/README.md#scripted-e2e-implementation) owns fresh serial model selection, promotion/advice, task/session limits, signed live adjustments and resumable close-out. Launcher-owned staging, commit and `git push` after every accepted task; every three completed close-outs adds a resumable Sol High lessons/composition audit with a refactor commit and push. Explicit literal paths exclude unrelated work and output artifacts; existing grants, safe session-boundary stop and guarded owned cancellation/cleanup apply. |
| Complete host category | `tools/run-tests host [--continue-on-errors]` | All host work, including publishing, two fresh builds and comparison, in the aggregate's four branches; no VM discovery, authorization or execution |
| Complete VM category | `tools/run-tests vm [--vm NAME] [--continue-on-errors]` | System and ready E2E coverage; required package inputs are prepared automatically; independent host runs may overlap |
| Combined complete categories | `tools/run-tests host vm --vm NAME` | Equals `all`; `vm` expands to `system e2e`; any subset/order is accepted, scheduled host first, then sequential system and E2E; one report and shared package inputs; combined runs reserve both scope locks |
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

The [runner contract](../tests/README.md#all-established-regressions) owns
failure-stop flags; [reconnection](../tests/README.md#aggregate-execution-and-reconnection)
owns terminal independence, scope-specific attachment, cancellation and unread
results. Host and VM namespaces are independent. Explicit VM runs retain their
canonical selection; default queue runs can attach without `--vm`. Help, listing
and collection remain read-only inspections, never acceptance or execution.

The [repair launcher contract](../tests/README.md#scripted-repair-loop) owns
option forwarding, retries, diagnostic handoffs and agent isolation. Reattachment
does not execute new selectors. Checkout-tool changes activate on invocation
(`none`) without installing or restarting the product on the development host.
Selected guest lifecycle tests retain their installation and restart requirements.

Bulk output, scratch, reconnect state and retained exports use gitignored,
disk-backed `output/test-runs/`, with separate host and privileged ownership.
Legacy `/tmp/onpc-*` paths remain readable inputs, not new bulk output targets.
The [storage mandate](Mandates/Test-Storage-Mandate.md) owns allocation and
exceptions; [retention](../tests/README.md#aggregate-output-retention) owns
rotation, owner-locked reclamation and identity-audited legacy migration.

When starting a new run, system and E2E listings run as the ordinary user without safety tests, privilege
or VM mutation. `fast --list` forwards `LIST=1` once its target exists. `all`
accepts no narrowing arguments. Reserved entry points do not claim that the
corresponding suite is implemented or passing. Future aggregate work must reuse these routes
and the existing inventory/lease, including internally invoking the validated
system/E2E dispatcher. It must not introduce unrestricted Make arguments or a
second suite inventory. Current E2E execution accepts `--artifacts` and
`--scenario` under the [runner contract](../tests/e2e/README.md#run-e2e-scenarios);
extensions must preserve the same guarded ownership and evidence contract.

Pytest options are intentionally bounded: quiet/verbose, exit-first, capture,
collection, warnings, `-k`, `-m`, maxfail, durations and traceback style. A scoped
`--ignore=tests/<category>/...` accepts validated file/directory patterns.
Configuration, plugins, arbitrary output paths and response files are refused.
Interpreter/plugin/loader/compiler/Make environment overrides are removed.
Coverage and build outputs use the shared disk-backed storage helpers; follow
the [test storage mandate](Mandates/Test-Storage-Mandate.md) for allocation and
the [artifact access contract](../tests/README.md#prompt-free-test-artifact-access)
for reading retained output.

Cleanup performs only serial, identity-checked recovery and reclamation before
parallel test scheduling. It never launches cleanup-safety regressions, collects
pytest cases, hashes a regression qualification cache, or creates cleanup test
buckets. The privileged dispatcher executes only the selected controller with
the existing authorization, retention, VM lease and live ownership checks.
Actual cleanup remains complete: reap owned children, restore recorded VM state
when required, reclaim recorded scratch and rotate registered output while
preserving foreign/replaced resources and failure evidence. A recovery refusal
still blocks the operation. Idle cleanup should take seconds or less; necessary
process settlement or VM restoration must finish rather than be abandoned to
meet a time limit.

Cleanup-safety regressions remain in explicit unit/host/all selections. Validate
changes to cleanup with the relevant tests during development; introducing a new
cleanup implementation still requires its corresponding regression. No runtime
passing-test receipt substitutes for live ownership checks.
Collection/listing does not run cleanup or claim passing test coverage.
Host-only startup and `tools/cleanup-e2e --host-only` reconcile interrupted host
retention under its activity and storage owner locks, without VM configuration
or privileged dispatch. Recovery validates recorded identities and preserves
evidence in bounded retention; active owners and replaced resources still refuse.
For interrupted online startup, an off graphical guest whose attempt never
recorded an instance may still carry its saved app snapshot's run tag. Serial
cleanup requires the exact private snapshot record, unchanged baseline/storage
and safe isolated domain before restoring it. This permits no live-instance
adoption, startup or shutdown; unproven identities still refuse.

## The configured test VMs

All VM consumers inherit the
[observation mandate](Mandates/VM-Mandate.MD#vm-observation-mandate) and
[target-selection contract](Mandates/VM-Mandate.MD#target-selection).
Those owners define shared watch intent/transport, per-tool selectors, enabled
defaults, concurrency, cancellation and canonical identity. Host-only tests,
help and listing need no enabled VM. Maintenance requires one explicit registered
target; queue-capable launchers select only their validated registry entries.
Each guest retains its separate lease and evidence journal; unfinished legacy
journals remain blockers until recovered.

The [runner reconnection contract](../tests/README.md#aggregate-execution-and-reconnection)
owns attachment and cancellation of explicit selections and default queues.
Current IDs may identify the same retained canonical guest, never adopt another
guest after renumbering. `tools/watch` and `make watch` observe all registered
VMs without a VM parameter; viewing does not authorize VM mutation.

`tools/test-vm` accepts this configured-name selector and no URI, disk, XML or
snapshot-name input. Its `exec` action accepts arbitrary guest command arguments
after a mandatory `--`, never an arbitrary host command. It uses `qemu:///system` and the UUID
pinned separately for that name from its root-private finalized baseline
provenance during setup. Setup refreshes pins for all configured entries.
A missing baseline
disables this route until preparation and a tools refresh; it never selects a
replacement by name alone.

| Command | Effect |
| --- | --- |
| `tools/test-vm --vm NAME status` / `xml` | Inspect only the pinned guest using a read-only connection |
| `tools/test-vm --vm NAME snapshots` | Read snapshot names and saved XML for only that pinned guest; never restore or change a snapshot |
| `tools/test-vm --vm NAME exec [--timeout SECONDS] -- COMMAND [ARG ...]` | Execute as guest root in the current owned online app-snapshot maintenance instance; reuse saved private credentials, strict SSH host-key and guest identity checks, shared observation and the exclusive lease; preserve guest state and return its command status |
| `tools/test-vm --vm NAME reproduce-gdm-denial` | Diagnostic-only replay of the shared fresh-child zero-time journey through its bounded Cancel sequence; close the graphical worker and retain the owned online guest before final account-list observation, for `exec` probes followed by `stop`. No acceptance credit. |
| `tools/test-vm --vm NAME reproduce-lock-denial` / `reproduce-retained-entry` | Replay the shared child denial or retained two-child history in the same owned maintenance envelope, stopping before the native restriction read or restricted curtain read respectively. Close the worker and retain the guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-transfer-refusal` / `probe-transfer-refusal` | Replay the shared overlay-to-kiosk history up to Riley's wrong-surface refusal, or read that refusal in the retained child session. Keep the guest for guarded `exec` diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-remembered-return` / `probe-remembered-return` | Replay case 58 through Jordan's return credential and retain a desktop read at that boundary before worker shutdown, or read the retained child session again. Keep the guest for guarded `exec` diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME repeat-remembered-return` | From that retained Jordan scene, replay Riley's retained transfer and Jordan's return using the same helpers, retaining the desktop read and guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME enter-remembered-return` | Start a new guarded Jordan return challenge from the owned reproduced greeter, retaining the desktop read and guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME probe-lock-curtain` | Run only the shared read-only child curtain observer in the current owned maintenance scene, retaining guarded command evidence; never reveal, authenticate or unlock. |
| `tools/test-vm --vm NAME rename --new-name LABEL` | Rename the idle, powered-off pinned UUID, preserve snapshots and disks, and move its private provenance directory; refuses existing destination state and unfinished controllers |
| `tools/test-vm --vm NAME rename-disk` | Rename the idle pinned guest's single QCOW2 image to `NAME.qcow2` in its existing directory; update domain/internal-snapshot references and provenance, preserving bytes and inode; refuses overlays, shared disks, destination collisions and unfinished controllers |
| `tools/test-vm --vm NAME start` | Acquire the shared lease, validate provenance/disks/snapshot, restore the outer baseline, record and boot an isolated maintenance attempt |
| `tools/test-vm --vm NAME reboot` | Request an ACPI reboot of that same recorded running instance; preserve guest state |
| `tools/test-vm --vm NAME send-key 28` | Send 1–16 numeric Linux keycodes (1–255) to that instance; no shell or host command |
| `tools/test-vm --vm NAME screenshot` | Capture the owned running guest through the legacy `/tmp/onpc-vm-screen-*` allocation; migration to [shared storage](Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes) remains required. This is separate from the caller-owned PNG export exception. |
| `tools/test-vm --vm NAME stop` | Stop only that recorded maintenance instance, verify/restore the outer baseline and original domain configuration, leave it off |
| `tools/test-vm --vm NAME reset` | Restore the accepted outer baseline while idle, leaving the VM off |
| `tools/test-vm --vm NAME recover-online ID` | After explicit authorization of the inspected instance, recover an interrupted online start with matching maintenance, snapshot and isolation proofs; restore the baseline and leave it off |

Every mutation shares the runner's nonblocking exclusive lock. Reopened
maintenance operations require a matching root-private ownership record,
run/domain instance, original configuration, baseline digest and snapshot digest.
Other active controllers and replaced identities are refused. No new domain,
snapshot, clone, overlay, arbitrary XML, host-device attachment or general
host shell is exposed. Guest root commands have no program allowlist; shell
programs and interpreters execute only inside the isolated guest. No reset occurs
between reboot/input/probe steps. Probing neither starts nor restores a guest,
rotates its keys nor adjusts its clock. It requires the current online app
snapshot's private credential record and the existing maintenance ownership
journal; manually started guests and active test controllers are refused.
The default command deadline is 120 seconds; `--timeout` accepts 1–86400 seconds.
This is finite command execution, without an interactive terminal.
The probe authenticates as guest root independently of the foreground desktop
and lock state. Customer-journey foreground/unlocked preconditions are not
maintenance authorization checks. For an explicitly requested session renewal,
the shared `tests/e2e/session_control.py maintenance-logout UID SESSION` entry
binds that root operation to one observed desktop and retains other desktops.
It invokes GNOME's normal logout as the target user while keeping the observer
root; it neither forces termination nor retries uncertain input.
Private key copies and command artifacts remain in shared root-private scratch;
stdout/stderr return to the authenticated caller and the existing filtered watch
transcript. Setup refresh installs this route and any missing OpenSSH client via
`./setup.sh --test-tools-only`, without new Polkit actions or general SSH grants.
The direct `tools/test-vm` and `./tools/test-vm` prefixes already approve every
guest command after `exec --`, including guest shells and interpreters, for
current configured IDs and names. Probing any entry in `config/test-vm.json`
has standing user authorization, including entries disabled for test scheduling;
do not request command approval or developer confirmation. The installed
test-runner Polkit rule grants the active local administrator automatically,
and unavailable authorization fails noninteractively without a dialog.
Do not add selector-specific or host-shell
grants. Keep the host invocation a simple literal command: complex embedded
quoting can prevent Codex's shell parser from extracting the launcher prefix.
For large guest scripts or text payloads, pass a shell-quoted literal encoded
argument and decode it inside the guest rather than embedding multiline source
or shell quote concatenations. Encoding changes transport only; guest identity,
ownership, observation and authorization checks still apply. A rules refresh
does not change that parser boundary or reload the current Codex process.
For binary artifacts, use `tools/test-vm --vm NAME exec --input-file 'PATH' -- COMMAND`.
The unprivileged launcher opens a regular, non-symlink file of at most 64 MiB and
passes its descriptor as stdin. Privileged code never opens the supplied host
path; it validates finite regular-file input and sends its bytes through the
same guarded SSH transport in one operation. Input bytes are filtered by the
existing private-input observation path. Pipes, interactive stdin, oversized
files and changed sizes are refused; ordinary `exec` never reads stdin.
Rename accepts only a destination label, preserving the UUID and disks. It
records original metadata before mutation and rolls back checked failures;
interrupted records remain a refusal gate. After renaming, update `name` in the
shared config, refresh test tools, and prepare a matching baseline through the
existing auto-mode route before tests. Domain display names preserve case;
guest hostname consumers derive the lowercase form from that same config.
Historical snapshot domain names remain intact. Only exact saved metadata
attested in the private rename record can use a historical name; libvirt keeps
the current domain name when restoring those snapshots.
Disk rename accepts no filename or path argument. Its private journal records
exact original metadata before mutation and gates interrupted transactions.
Checked failures roll back only the owned image and references. Update that
entry's `disk_anchor` in `config/test-vm.json` immediately after success;
the operation does not write checkout configuration as root. Internal snapshots
are metadata-redefined without restoring or deleting them, retaining their
current selection. Baseline proof and image bytes remain intact. Previously
cached app snapshots retain their original baseline digest and must pass the
ordinary reuse checks before use.
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
identity-checked recovery and exclusive leases;
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
The direct `rg -n` allowance already covers regex/path variations; another
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

`codex execpolicy check` tests an argument vector,
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
