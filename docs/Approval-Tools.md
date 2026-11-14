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
| E2E prerequisites | `tools/cleanup-e2e` for recorded leftovers; add `--discard-completed` only when discarding saved execution results is explicitly authorized, under [retention ownership](../tests/README.md#aggregate-output-retention); `tools/prepare-appsnapshot --vm NAME --y --overwrite true\|false` for the current online version snapshot through the pinned dispatcher and shared VM lease |
| Publication | Direct `tools/publish.py` once publication itself is authorized; see [publishing](#publishing) |

Invoke approved commands directly. Correct quoting and command shape before
interpreting a failure as missing authorization. When local sockets or ownership
metadata require execution outside the sandbox, use the existing scoped helper
grant. Do not add duplicate rules, broad shell/interpreter grants or permission
prompts to work around restrictive policy.

The general host Python rule explicitly prompts, even when an older or narrower
allow rule also matches: the most restrictive decision wins. Do not use ad hoc
host interpreter commands to assemble routine reports or edit text. Use the
existing launcher/artifact routes and native `apply_patch` for authorized text
edits. A repeat prompt on those interpreter commands is expected policy, not a
missing allow rule to repair.

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
For a recorded interrupted qualification build with no published manifest,
`tools/cleanup-e2e --vm NAME --discard-unpublished-input CHECK` recovers only that
exact host allocation under the [storage contract](Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes).
It preserves valid bundles, reports and journals and performs no VM operation.
For an evidenced input wrongly registered to the batch rather than its VM,
`tools/cleanup-e2e --vm NAME --transfer-batch-input CHECK` preserves the verified
bundle and transfers its cleanup ownership under that same storage contract.
Its baseline probe is read-only; it does not start or restore a VM. Pending
transfers require the identical guarded recovery, never manual journal edits.
Standalone snapshot package bundles use
`tools/cleanup-e2e --vm NAME --transfer-batch-appsnapshot ALLOCATION` with the
exact recorded allocation basename and the same nondeleting ownership guards.
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

### Portable Codex configuration

Clone the repository and run `./setup.sh` on a supported desktop, or
`./setup.sh --server` on a supported automation server. Both install host
read policies and validate the tracked [project configuration](../.codex/config.toml)
and [command rules](../.codex/rules/tests.rules). Trust each checkout in Codex
and restart Codex after setup or tracked rule changes. Setup never marks
directories trusted automatically.

These portable files arrive with every clone/worktree. They contain no absolute
checkout paths, credentials or personal state. The current workspace is writable
under Codex's workspace-write sandbox without an additional absolute write root.
Other files under `.codex/` remain ignored. Setup validates shared files without
rewriting them; unchanged host rules and user configuration are left untouched.

Desktop setup adds absent tables from
[`config/codex-desktop.toml`](../config/codex-desktop.toml) to the user's
`CODEX_HOME/config.toml` (default `~/.codex/config.toml`) when the bundled
marketplace exists. Existing personal tables are preserved. The resolved local
marketplace path stays outside Git. These defaults apply to other projects for
that user too. Initialize the desktop app, then rerun `./setup.sh --test-tools-only`
if integrations were unavailable. Headless setup does not add desktop settings.
App-owned MCP/browser wiring and caches remain managed by the app.

The tracked machine read policy now includes ordinary file readers, pipeline
filters, checksums and public `curl -fsSL` fetches previously dependent on saved
personal approvals. The repository `AGENTS.md` includes their quoting guidance.
Historical personal grants for unrelated projects, raw VM commands and privileged
utilities are not imported: maintained project guards and diagnostics remain the
authority. Obsolete `.codex-staged-*` snapshots are ignored and unused.

Provision signing configuration/private keys, SSH/Git credentials,
Codex login, plugin account connections and `~/.onpc-config/.envrc` secrets separately on each
host. Server setup supplies missing checkout-local Git identity as described below;
other modes only report missing identity. Setup preserves existing Git settings
and reports missing upstream;
it never copies authentication, private keys, session history or personal trust
lists. See [signing setup](Publishing.md#noninteractive-signing) for publishing.

### Local state and worktree portability

The user's private `~/.onpc-config/.envrc` is shared across all checkouts and worktrees on
that host; checkout-local `.envrc` files are not read.
Besides `~/.onpc-config/.envrc`, keep `.aws/`, Codex login/trust/plugin caches, SSH/signing keys
and `~/.config/copr` credentials local. Only the two allowlisted `.codex/` files
are shared. Git configuration (identity, signing and publishing-checkout selection),
hooks and worktree metadata also belong to the host, not the source tree.

The tracked `config/environment.json` is operational configuration, not a portable
machine template: branch `repo_root`, backup paths, VM disk anchors and SSH host
selections must match the destination host. Check these before running launchers;
a new worktree does not provision equivalent VMs or remote aliases. Keep
credentials out of that file.

Recreate `.venv/` environments with setup instead of copying them. Builder images,
installed helpers/Polkit grants and registered VMs are host resources. Runner
`artifacts/`, `output/`, diagnostic downloads, caches and generated locale files
remain ignored runtime/build state. Obsolete `.codex-staged-*` snapshots are unused.

The tracked [VS Code workspace settings](../.vscode/settings.json) exclude
`output/`, `artifacts/`, `.venv/` and `.worktrees/` from recursive file watching
and normal searches. Keep these exclusions enabled: generated files and temporary
propagation worktrees can otherwise trigger an extension search for every file
created or deleted. Git ignore rules alone do not prevent those events, and an
extension can supply its own search exclusions. VS Code's
[recursive watcher exclusions](https://code.visualstudio.com/api/references/vscode-api#workspace.createFileSystemWatcher)
prevent the triggering events without changing the shared storage location.
These relative settings travel with Git and apply when VS Code opens any checkout
containing them; setup does not copy them into a host's user profile. Propagate
settings changes through the [shared worktree workflow](Execution-Plans.md#shared-worktree-propagation)
so every configured branch receives them. Existing checkouts need that update and
a VS Code window reload; a fresh clone of an updated branch already includes it.

### Setup modes and activation

Run `./setup.sh --test-tools-only`, then restart Codex with this checkout trusted.
Setup installs root-owned helpers and scoped Polkit rules, pins the finalized
test baseline's VM UUID, and validates tracked project-relative command prefixes.
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
After a tracked project rule correction, start
a fresh Codex process. Each launcher agent is a fresh process, so its next session
loads refreshed rules; an already-running agent keeps its original policy.
The embedded resolver checks repository markers, ownership, permissions and
symlinks before loading checkout code. It does not replace Polkit authorization.
First install uses `./setup.sh --bootstrap-tools` and can require administrator
authentication to establish the grant. Repeated bootstrap and routine refreshes
reuse the dedicated `onpc-setup` helper without asking for authentication.
Repair of an existing denied installation requires running that setup mode from
an administrator-authorized root session; it never falls back after denial. For Codex-only
host read-policy changes, use `./setup.sh --test-tools-only`. Repeat setup after
changing installed helpers; adding tests within a supported category
does not require new approvals. A clean machine uses full `./setup.sh` for
dependencies and host policies on Ubuntu or Fedora Workstation 44, from a host
terminal rather than a Flatpak runtime. Ordinary setup does not require VMs.

For an Ubuntu Server 26.04 or newer automation host, run `./setup.sh --server`
as the administrator account that owns the checkout, without prefixing the
command with `sudo`. On first headless setup only, it requests terminal-based
`sudo` authorization to install the fixed helpers and opt that account into
SSH/background execution. Subsequent runs reuse the installed noninteractive
grant and stop on denial, without retrying authentication. The account must
remain in `sudo`; setup refuses root-owned checkouts and direct root invocation
of this mode so builder images, the UI environment and checkout rules stay
user-owned. An existing desktop installation can opt in through the same first
headless bootstrap.

Server setup also establishes the executing machine's
[VM host assignment](../tests/integration/Environment.md#shared-vm-configuration).
Run it from that server's registered branch and checkout. Existing servers need
one `./setup.sh --server` run after receiving SSH preparation support; ordinary
helper refreshes preserve the installed host assignment.

Headless setup shares the development/build/UI-test dependencies, installs the
VM-host libvirt/QEMU inventory (including Python libvirt and guestfs bindings),
refreshes development helpers and graphical-host AppArmor policies, and prepares
the caller-owned Fedora RPM builder. It disables APT recommendations to avoid
pulling in a desktop through optional dependencies; GNOME/Mutter/GTK libraries
needed by isolated UI tests are still installed. For each missing or empty Git
`user.name` or `user.email`, it sets a checkout-local default of
`Puffy Slippers Tech LLC` or `dev@tech.puffyslippers.com`, respectively, matching
this project's commit identity. Existing effective values are preserved. These
defaults also apply to linked worktrees of the same clone; account-wide Git
configuration and unrelated clones are unchanged. It preserves signing
configuration, remotes and credentials, reporting any remaining unusable identity
or missing branch upstream as actions needed. It checks Git remote read access without
prompting; push permissions must be configured separately before using committing launchers.
Setup prepares the selected agent's user-owned policy through the fixed adapter
boundary, preserving personal settings and trust. The fixed privileged
`codex-rules` operation still manages only the machine-wide Codex read policy;
it grants no other provider installation or policy writes. An unqualified agent
selection reports action needed without preparing its native policy or falling
back to Codex. Setup never installs or authenticates a coding CLI.
Headless setup installs neither VS Code nor its Watch extension.
Headless setup installs OpenSSH Server, validates the existing sshd configuration,
and enables/starts `ssh.service`. It preserves host keys and authentication policy.
If UFW is already active, setup allows TCP access to the ports reported by
`sshd -T`; it neither enables UFW nor changes unrelated firewall rules. Other
firewalls and network/router access remain administrator responsibilities.
Setup prints the active SSH ports. Its checkout stage ends with a connection
summary containing server host-key fingerprints, the account, current network
addresses, checkout path and registered Git worktrees. Setup ends with readiness
for the agent selected by that checkout, using the executing account's native
environment. Codex discovery preserves Node/NVM support without loading
interactive shell startup files; its login-status check has a 15-second limit.
The checkout stage also performs a read-only Git remote probe with a 20-second
limit. These checks never prompt for login and report missing readiness without
discarding successful setup. Resolve any
action-needed items before starting a launcher. The summary stays in terminal
output, outside Git. Configure machine-to-machine SSH separately on the client,
including the alias, trusted server host key and public-key authorization.
Never copy private keys between hosts. Confirm
`ssh -o BatchMode=yes myserver true` succeeds before configuring a
[Watch SSH source](../vscode/onpc-watch/README.md#local-and-ssh-sources).
The client SSH alias and Watch source settings remain client-owned.
To refresh development helpers on a registered host using the invoking branch's
current source, run `./setup.sh --test-tools-only --host HOST`. The shared source
transfer runs the normal setup entry point in private scratch; it preserves the
host's checkouts and existing authorization. This explicit setup route also
updates older helpers before VM operations use transferred source.

On the development computer, run `./setup.sh --connect-server`
to verify existing SSH access to every configured SSH host and install Watch.
It reads the launching branch's host and the other hosts' branches from
`config/environment.json`, including hosts disabled for VM scheduling. The command is noninteractive and requires
no terminal or server selection; missing prerequisites fail with an error.
The alias is always `host.name`. OpenSSH owns its address, username, port,
identities and proxy settings. Setup uses that alias directly without changing
SSH files. Shared tool dispatch uses the optional registry `ssh_port` when
provided; otherwise OpenSSH selects the port. Keep an explicit registry port
consistent with the alias's port.
The first branch entry for each host supplies its starting checkout;
all configured branch paths are displayed without asking for them again.
Setup verifies noninteractive SSH with `BatchMode=yes`, strict host-key checking
and a 15-second connection timeout. It prompts for no address, username or
password. Failed verification reports the SSH error and directs the user to
complete machine-to-machine setup separately, including loading a locked key
with `ssh-add` when needed. Setup does not generate keys, run `ssh-copy-id`,
accept new host keys or write anything under `~/.ssh`.
Connection details stay out of command history and tracked files.
Only one starting checkout is needed per server: Watch discovers the other
registered Git worktrees through Git metadata. Server setup lists those
worktrees automatically. Independent clones are not
discovered through that relationship and require separate Watch sources.
Profiles generated by older setup versions are not migrated or removed. If one
overrides the desired alias, reconcile it manually during machine SSH setup;
the current command preserves existing SSH configuration and keys.

After verifying noninteractive SSH and each remote Watch reader's prerequisites,
setup installs the Watch extension. Open the local checkout in VS Code, reload
the editor if needed, then use **ONPC: Watch**. With `onpc.watch.sources` empty
(the default), Watch automatically connects to the local checkout and every SSH
host with a configured branch, and its controls act on the launcher’s own host.
Click **Reconnect** after changing the registry. Explicit sources override this
automatic discovery; remove such an override to return to the default.
Setup creates no separate workspace or source settings. Private workspaces
created by older versions remain unchanged and are no longer needed for this flow.
Usernames, addresses and keys must never be copied into tracked configuration
or examples. Remote checkout paths may be public. This mode starts no tests and
does not provision remote Git credentials or Codex login.

For unattended availability, headless setup persistently masks `sleep.target`,
`suspend.target`, `hibernate.target`, `hybrid-sleep.target` and
`suspend-then-hibernate.target`. This also prevents ordinary idle/lid-triggered
suspend on a desktop laptop acting as a server, without restarting its desktop
session. Keep it on external power; battery exhaustion and network loss remain
possible. Reserve its Wi-Fi address in the router's DHCP configuration.
To restore normal sleep when retiring the server role, an administrator can run
`sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target`.
Account credentials, Codex installation/login and editor connections remain
administrator responsibilities. Setup reports absent Codex CLI as an action needed.
Remote branch launchers preserve the SSH account's environment. If Codex is
absent from its noninteractive PATH, they load NVM from `NVM_DIR` (default
`~/.nvm`) to expose its default Node installation and Codex. They do not source
interactive shell configuration. Other user-local installations must be exposed
on the noninteractive SSH PATH; authentication belongs to that same account.
Rerunning `./setup.sh --server` applies these additions to an already configured
host through its existing noninteractive grant; no fresh bootstrap is required.

This mode reuses `--vm-host-only`'s dependency inventory and helper/policy refresh
without installing the VS Code extension or virt-manager GUI. It does not
configure VM networking/storage or create/prepare VMs and baselines. Shared helper
refresh preserves the existing finalized VM identity checks; it does not operate
a VM. Successful headless setup establishes the development and VM-host
environment, not installed VM acceptance. The ordinary
terminal launcher interfaces, detachment and reconnection remain unchanged.

The opt-in grant is root-owned `/etc/polkit-1/rules.d/49-onpc-headless.rules`,
with a public root-owned account marker at
`/usr/local/libexec/onpc-headless-account`. It authorizes only the selected
administrator account and the five fixed development-helper actions/programs,
including their detail-free authorization prechecks. Other users retain the
desktop rules. Both desktop and test-tools refreshes preserve the opt-in grant;
they do not silently enable or revoke headless access. A different account or an
unsafe marker/grant requires administrator repair. Headless setup refreshes
the managed rule from current source while preserving the designated account.
To revoke headless access and permit a later explicit bootstrap, an administrator
removes both managed files. Their absence restores the ordinary desktop policy.

`--vm-host-only` adds libvirt/QEMU and installed-test host prerequisites and
refreshes helpers/policies without preparing or starting a VM. On Ubuntu, full
setup and `--dependencies-only` also prepare the caller-owned Fedora 44 RPM build
image. Fedora installs native RPM build prerequisites and prepares a caller-owned
Ubuntu 26.04 DEB build image. Both hosts default to both package formats.
`--rpm-build-tools` selects just that host's RPM route; PPA tools are
Ubuntu/Debian-only. Refresh an older installed setup helper with
`--test-tools-only` before using a new mode. Builds never install prerequisites.
Explicit baseline preparation is
`tools/prepare-vm --vm NAME --mode auto|manual [--y]`; launcher/session
work includes `--y`, while manual work omits it to retain confirmation. See
[VM prerequisites](../tests/integration/Environment.md).
Reusable guest dependencies, fixed fixture apps/launchers and persistent harness
settings belong to this baseline route under the target-specific
[baseline mandate](Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
Ubuntu and Fedora schema-4 captures exclude movable fixture apps, launchers,
admissions and copied fixture sources.
Test runners and app-snapshot
preparation verify them and report missing or stale state; they never install or
repair them implicitly. Invoke authorized baseline refresh separately. Its finite
inventory must reconcile idempotently, preserve unrelated state and safely retry
owned partial work; see the [baseline mandate](Mandates/VM-Mandate.MD#vm-host-setup-and-baseline).
The host account owns fixture input folders. The maintained SSH provisioner
reads selected inputs without changing host ownership and resolves guest owners
from accepted roles; no host/guest UID synchronization is required.
The tools-only refresh also fills missing `curl`, `ripgrep`, Python coverage
plugin and GTK 4 VTE viewer packages without requesting package upgrades; ordinary test commands
never install dependencies. Full setup includes these prerequisites too.
For an additional worktree on a configured host, `./setup.sh --ui-tests-only`
creates its checkout-local UI environment from the pinned requirements. This
unprivileged mode changes neither host package versions nor Git configuration;
missing system prerequisites still require the normal dependency setup route.
For two server worktrees, reserve different branches/checkouts for `fix-tests`
and other task launchers. Run full `--server` setup once; in the second
user-owned worktree run `./setup.sh --ui-tests-only`. The account grant and
builder images are shared; checkout environments and launcher state are separate.
Tracked Codex settings and rules arrive with the worktree. Completed commits
still follow [configured branch propagation](Execution-Plans.md#shared-worktree-propagation),
which can merge into the other checkout. Worktrees do not reserve independent
VMs; existing host-wide VM leases remain authoritative.
`./setup.sh --watch` installs or updates only the caller's VS Code watch
extension through the available `code`, `code-insiders` or `codium` CLI, without
administrator privileges or dependency setup. Full setup and tools refresh also
install it when that CLI is present. Reload VS Code and use **ONPC: Watch** from
the Command Palette in a trusted checkout; see the
[extension guide](../vscode/onpc-watch/README.md).

The [rules renderer](../tools/install_codex_rules.py) validates its required
launcher inventory, then discovers every regular executable under `tools/`
without following symlinks. The user preapproves direct project-tool execution;
the tracked generated rule contains the exact `tools/` and `./tools/`
executable paths. Run these commands with the intended checkout root as the
working directory; the same rules then apply across worktrees and local
enlistments without embedding checkout locations. Installed system helpers keep
their fixed absolute paths. This includes validated launcher actions and
argument orders. After adding/removing executable tools or editing the rule template,
regenerate with `python3 -IB tools/install_codex_rules.py --write-rules` and commit
`.codex/rules/tests.rules` alongside the change. Setup validates the inventory. Codex matches literal argument tokens,
so a `tools/*` string is not a directory-wide grant. General shells/interpreters
and arbitrary privileged wrappers retain their restrictions. The tools' own
argument validation, task authorization and VM/Polkit guards still apply.
Simulated checkouts must copy that complete inventory too.
A missing required launcher is a test-fixture failure, not a reason
to weaken rendering validation or refresh host permissions.

Routine setup tolerates only missing grants for newly added optional executables
when the saved policy otherwise exactly matches the template and retains the
required launcher grants. It warns with the missing paths and leaves all rules
unchanged, so unrelated VM validation can continue. Those new tools still need
regeneration and a fresh Codex process before unattended use. Removed tools,
missing required grants and other policy changes remain fatal. The renderer's
`--check` remains strict about the complete current inventory.

Development-helper Polkit actions bind these exact executable paths and default to `no`,
so missing authorization rules cannot trigger an authentication dialog. The
wrappers query their own process identity without action details, which Polkit
reserves for trusted callers. Polkit authorizes these programs for an active, local member of
the host's administrator group (`sudo` on Ubuntu, `wheel` on Fedora). The installer
renders only that group's check into each desktop development rule. The explicit
headless grant above additionally permits its designated administrator account
without an active local session. Other callers receive a denial, without an authentication
dialog. The checkout launchers check that authorization noninteractively before
using `pkexec`, so a missing installation or unavailable grant fails with setup
guidance. They do not enable password caching, authorize general privileged
interpreters, or grant libvirt control to all domains.

Interactive [request previews](SystemDesign/Frontends.md#responsive-request-layout)
instead use a separate authentication-only action with `auth_admin`, without
retained authorization or an executable binding. The checkout owner's UID may
supply its localized product prompt details. This grants no product privileges;
the preview mocks the grant after real administrator authentication.

The executable binding uses Polkit's documented
[`org.freedesktop.policykit.exec.path` action annotation](https://polkit.pages.freedesktop.org/polkit/pkexec.1.html),
with [default denial](https://polkit.pages.freedesktop.org/polkit/polkit.8.html)
and the scoped local-administrator rules applied separately.

Use Codex's ordinary escalation mechanism with the loaded helper prefix when
local sockets, system D-Bus or root-owned metadata require execution outside its
sandbox. Sandboxed owner remapping can look like an invalid installation; verify
that context before reinstalling or interpreting it as a host-policy denial.
The helper reports the observed UID and mode separately from an unsafe file type
or writable mode. Ownership refusal never relaxes the guard or establishes a
host installation defect. After establishing that a session has stale helper
policy, start a fresh session under the current grants; do not change ownership
or broaden authorization to bypass the refusal.

Development activation is `none`: installed helpers change on their next
invocation, Polkit watches its rule directory, and Codex loads rules on restart.
The standalone app-snapshot route requires the current installed test dispatcher;
refresh it with `./setup.sh --test-tools-only` when adding these tools. It shares
the existing test-runner Polkit action, owned recovery and fixed VM UUID, without
adding general snapshot or libvirt permissions.
Automation and agent sessions include `--y` for authorized preparation.
Manual work omits `--y` to confirm before preparation. Selection and rolling
concurrency follow the [VM mandate](Mandates/VM-Mandate.MD#authority-and-operation),
including lists, `all-enabled` and `all`. Omitting `--vm` selects `all` eligible
online VMs for baseline preparation in both modes; app-snapshot preparation
uses the same eligibility rule. Both VM and host enabled flags must be true.
The flag preserves all authorization, lease, ownership and validation checks.
Standalone app snapshots are always online; there is no `--mode` parameter.
`--overwrite` defaults to `true`; supplying the flag without a value also means
`true`. Automation and agent sessions must explicitly pass `--overwrite true`
to rebuild or `--overwrite false` to reuse a fresh matching snapshot without
building. Manual use may omit it to rebuild by default.
The verified baseline selects Ubuntu 26.04 DEB/APT or Fedora Workstation 44
RPM/DNF preparation. Fedora uses the maintained native/Mock/rootless container
builder and preserves enforcing SELinux during offline SSH bootstrap and installation.
Preparation leaves the restored running guest in the existing VM-maintenance ownership
journal. Its restore-only dispatch uses maintenance scratch rather than an
evidence-retention session, whose entry gate requires an idle VM. The shared
owned recovery and live VM ownership checks still apply. Offline snapshots and online
snapshots older than 24 hours force replacement. Explicit overwrite still rebuilds.
Standalone app preparation holds the host-wide
[VM checkout](Mandates/VM-Mandate.MD#central-vm-checkout) throughout probing,
building and maintenance handoff. Other requests for that VM queue, including
requests from other checkouts; different VMs remain independent.
A read-only snapshot probe sends unfinished attempts through shared
recovery before probing again. Healthy online maintenance resumes directly;
replacement recovers its exact recorded owner through the maintained stop path.
Failed SSH or clock readiness after a successful restore performs owned cleanup.
Tooling activation is `none` on the development host. Guest snapshot preparation
still installs the declared product package and performs the required
restart; it supplies no customer-acceptance credit.
Graphical AppArmor policies are refreshed by full `./setup.sh`, `--server`,
`--vm-host-only` and `--test-tools-only` when libvirt's AppArmor profiles exist. Hosts without
libvirt skip this stage; Fedora retains SELinux and receives no AppArmor changes.
Development package dependencies belong to full setup or `--dependencies-only`;
VM dependencies belong to `--server` or `--vm-host-only`. Codex setup also installs its maintained machine-wide
`pwd`, `git status`, `rg -n`, `rg --files` and `sed -n` rules in `/etc/codex/rules/onpc-read-only.rules`, without
changing unrelated system/user rules. These reads cover any working directory
or repository; select a repository with the command tool's working directory.

## Git development

Routine Git development for this repository is preapproved through the project
rules: inspection, branches/worktrees, staging, commits, fetch/pull/push,
merge/rebase/cherry-pick/revert, stash, tags and remotes. Existing machine-wide
rules already allow `git status`. Run direct `git SUBCOMMAND` or
`/usr/bin/git SUBCOMMAND` commands with the intended checkout as the command
tool's working directory. Setup maintains this allowance from
[`config/codex-tests.rules`](../config/codex-tests.rules).

Quote revision operands as literal shell arguments as well as paths, including
ancestry and stash expressions: `git diff 'HEAD^1' 'HEAD' --stat` and
`git rev-parse 'stash@{0}^2'`. Codex's shell parser treats unquoted `^` and `~`
as possible expansion even for Bash, preventing the ordinary Git prefix match;
see the [parser and its literal-operand tests](https://github.com/openai/codex/blob/rust-v0.167.0/codex-rs/shell-command/src/bash.rs).
An argv-only policy check does not establish how the command tool parses a
shell string. Keep the direct command shape; do not
add duplicate Git grants or general shell grants to compensate for quoting.

The Git grant includes `git write-tree` for recording the staged tree during
commit recovery. It writes Git objects and may lock the index, so it needs the
same host execution route as staging and committing. Linked worktrees keep
their Git metadata beneath the original repository's `.git/worktrees/`; this
location does not change the selected branch.

For hunk-only staging, use direct `git apply --cached [OPTIONS] PATCH` with
`--cached` immediately after `apply`, including for `--check` and `--reverse`.
This narrow grant changes only the index and preserves working files, allowing
shared launcher close-out to exclude unrelated hunks. Plain `git apply` and
`git apply --index` are outside this grant. A read-only `index.lock` error can
mean the command missed its approved host route; inspect the exact argument
prefix before diagnosing a host filesystem failure. Actual denials remain blockers.

These prefixes trust Git, repository hooks and configuration. They neither
enforce the working directory nor validate trailing arguments. Use them only
for the authorized repository development task and preserve unrelated work;
discarding changes, deleting branches or rewriting published history still
requires explicit task authorization. This grant does not cover blanket Git
execution, `git clean`, `git reset`, arbitrary configuration or global options
before the subcommand. It does not authorize product publication.

Restart Codex with this
checkout trusted to load the updated rules.

### Source hunk ownership with existing grants

Ownership calculations use the same direct reader and Git grants as the rest of
close-out. Do not run ad hoc `python3 -c`, interpreter heredocs or shell wrappers
to transform content or calculate fingerprints. General host interpreters require
approval even for read-only code and cannot run in unattended sessions.

For a shared text file whose retained baseline contains only a SHA-256 fingerprint:

1. Read the retained baseline fingerprint, the complete current file and its Git
   diff. Identify the task's exact hunks from the accepted deliverable and session
   history. A candidate path or an arithmetic count change alone proves no ownership.
2. With native `apply_patch`, create a caller-owned unique `/tmp` text file
   reconstructing the current file with only those identified task hunks undone.
   Preserve all other content, whitespace and the final newline. Keep the source
   working file, index and ownership checkpoint untouched.
3. Run direct `sha256sum -- '/tmp/UNIQUE-baseline-candidate'` and compare its result
   with the retained baseline fingerprint. Record the reconstructed hunks and
   comparison in the recovery journal. An exact match supports that reconstruction;
   it does not assign ownership to any other hunk. A mismatch or an inability to
   reconstruct the bytes leaves ownership unresolved; do not stage ambiguous work.

`UNIQUE` is a placeholder. This uses existing native workspace edits and checksum
grants, with no setup refresh or new executable allowance. Do not guess global
numeric replacements to make a hash match. Actual policy denials remain blockers;
do not retry a denied interpreter command through another execution route.

### Destination work snapshots with existing grants

Before saving a dirty destination for propagation, inspect it from that
checkout's command-tool working directory with direct approved readers:

```sh
git status --porcelain=v1 --untracked-files=all
git diff --binary --full-index
git diff --cached --binary --full-index
git ls-files --others --exclude-standard
ls -ld -- 'path/to/active-file' 'path/to/untracked-file'
sha256sum -- 'path/to/active-file' 'path/to/untracked-file'
```

Use the actual paths returned by inspection. Git diffs preserve tracked content
and Git file modes; `ls -ld` records filesystem type and permissions without
following a final symlink. Hash only regular files, including untracked files;
inspect symlink targets through the listing and Git diff instead. Record absent
or deleted paths through Git status. Record the snapshot in the recovery journal
with native `apply_patch`; Git-generated patches may use `git diff --output`
as in the isolated staging procedure below. Keep commands direct and operands
quoted, without shell loops, redirections or interpreter wrappers.

These commands use existing reader and Git grants. Do not replace them with an
ad hoc `python3 -c` snapshot: general host interpreters require approval even
when their proposed code only reads files, so unattended sessions refuse them.
An actual denial still stops the operation; this recipe does not authorize
retrying a denied command or expanding permissions. Before saving work, confirm
the recorded branch, HEAD and active changes still match. After restoring with
the index state, verify the saved work against the snapshot, accounting for the
incoming committed changes. Retain backups on mismatch or conflict and follow
the shared conflict-resolution procedure.

### Isolated staging with existing grants

The commit skill uses direct Git commands for the entire transaction, including
when unrelated hunks are already staged. Environment-prefixed commands such as
`GIT_INDEX_FILE=... git commit` do not match the direct Git grant and can run in
the read-only sandbox. Do not use them for routine close-out or request new
environment/shell grants to compensate.

Preserve unrelated index work with reversible index-only patches:

1. Record the current HEAD and staged diff. Save the full staged diff with
   `git diff --cached --binary --full-index --output='/tmp/UNIQUE-staged.patch'`.
   Inspect session ownership and prepare a patch containing only the unrelated
   staged changes, preserving binary data and file modes where applicable.
2. Check and reverse that unrelated patch with direct
   `git apply --cached --check --reverse '/tmp/UNIQUE-unrelated.patch'` and
   `git apply --cached --reverse '/tmp/UNIQUE-unrelated.patch'`. Stage only the
   session hunks using `git apply --cached '/tmp/UNIQUE-session.patch'` or
   explicit owned paths. Review the entire staged diff before committing.
3. Commit, then check and reapply the unrelated patch with
   `git apply --cached --check '/tmp/UNIQUE-unrelated.patch'` and
   `git apply --cached '/tmp/UNIQUE-unrelated.patch'`. Verify that the saved
   unrelated staged content and all working files remain intact. Restore this
   work even if the commit fails; retain patches until restoration is verified.

Use caller-owned, unique temporary paths; `UNIQUE` above is a placeholder.
Create text patches with native `apply_patch` and let `git diff --output` save
Git-generated patches without shell redirection. The tracked grants for
`git diff`, `git apply --cached` and other approved Git operations accept their
trailing file operands, including random temporary names. No per-filename rule,
personal approval or rule refresh is needed. These grants are maintained in
`config/codex-tests.rules` and `.codex/rules/tests.rules` and travel with Git;
normal setup/trust activation still applies on a new host.

Keep these writes sequential. Recheck HEAD and staged content before mutating
the index; if another agent changes either, reconcile ownership against the new
state before continuing. Do not overwrite concurrent work with a stale index.
A restoration conflict follows the commit skill's conflict-resolution route.

## Publishing

Run `make publish` from the dedicated `releases/vX.Y` checkout to invoke the
single [publisher](../tools/publish.py).
On main, or alongside a running publisher in the same release checkout,
`make publish` connects to read-only publication monitoring instead.
It validates `docs/VersionHistory.md`, prepares the latest version and builds
local packages through queued disk admission for a fresh release, commits pending release-checkout changes,
signs, pushes
the source to that release branch and tags, submits missing DEB releases to
Launchpad through product-version gates, and verifies binary
repository publication. Pending or uncertain submissions are monitored without
resubmission. It asks for confirmation of a development pause before
directly merging committed release changes into main, then automatically
cherry-picking and pushing release metadata to main. Its
checkout-local publishing lock does not participate in development/build/test
activity locking. After the highlighted main-update handoff, development
continues independently of publication monitoring.
Its supporting modules are under `tools/publishing/`; they are not separate
release commands. RPM/COPR publication remains implemented but disconnected;
see [the channel wiring](Publishing.md#independent-channel-gates).

Local publishing checks run through the aggregate's `tools/run-tests publish` category
and the same module in `make test-all VM=NAME`. They create a private unsigned source
snapshot, run source integrity and Lintian checks, and build/test it in clean
sbuild. The same category runs the COPR source recipe, a clean offline Fedora
RPM rebuild, lint and runtime dependency resolution in private rootless
containers. See [local publishing tests](Publishing.md#local-publishing-tests).
They require no publisher credentials and never push or upload.

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
| `links` | Checks local inline/image and full, collapsed or shortcut reference-style links relative to each document, including same-document and Markdown heading fragments. Handles angle destinations, balanced/escaped parentheses, encoded spaces and optional titles. Masks code spans, fenced/indented examples and HTML comments without changing source offsets; never fetches URLs or evaluates input. HTML links are outside its syntax subset. |
| `words` | Counts whitespace-separated source words in one UTF-8 file, optionally between exact `--after`/`--before` markers. Each marker must occur once in the selected text; missing/ambiguous markers fail. Without `--before`, counts to EOF. |

Both accept regular files up to 8 MiB, refuse final symlinks/special files, and
expose no code, command, output-file or interpreter options. Link-check exits:
0 success, 1 missing targets/fragments, 2 invalid request/read failure. Failure diagnostics
give document argument number/line without copying prose or destinations.
Links from documents outside this checkout's `output/test-runs/` into that tree
are disposable report references. Routine `links` skips their availability and
fragments without opening, inspecting or invoking privileged readers; a nonzero
`skipped_reports` count appears in its summary. An explicitly supplied document
inside that output tree still receives ordinary target and fragment checks.
Other inaccessible destinations return 2 and are reported separately from
missing files. Explicit semantic `link_condition` and artifact-reader operations
retain their normal permission and integrity checks.

`tools/document_checks.py` owns the shared `Link` representation: character
offsets for the complete link, label and destination, use-site line, syntax kind
and Markdown-unescaped destination. Reference-style destination offsets address
the definition, while the complete-link offsets address its use. Definitions
are case-insensitive with collapsed whitespace; the first valid definition wins.
URL path/query/fragment separation precedes percent decoding, preserving encoded
filename punctuation. Delimited destinations retain terminal punctuation;
legacy code paths keep literal filesystem spelling, and bare evidence paths
trim sentence punctuation. Unrecognized or malformed
Markdown remains literal source rather than creating a reference.

Supported heading anchors use lowercase Unicode text, remove punctuation except
hyphens/underscores, replace whitespace with hyphens, and suffix duplicate IDs
with `-1`, `-2`, and so on without collisions. ATX and Setext headings, heading
code text, Markdown labels, escaping/entities, and quoted HTML `<a id="...">`
or `<a name="...">` anchors are supported. Non-Markdown fragments, including
reserved evidence selectors, remain available to their semantic owner; file
existence grants no evidence identity or acceptance. This reader assigns no
required/optional severity.

The parser bounds each UTF-8 source at 8 MiB, destinations at 8192 characters,
bracket/parenthesis nesting at 32 and reference labels at 999 characters.
`references` and `local_destination` expose syntax separately from evidence
validation. Legacy evidence collection uses `evidence_prose` to exclude link
labels, definitions and examples while retaining explicit code-delimited paths.
Protected queue comparison and rewriting use `simple_inline_references`, the
existing narrower grammar and conservative code masking: images, references,
titles, angle destinations, escapes and nested parentheses remain literal
protected claims.

The following evidence readers are optional archival tools for an explicit
inspection or repair request. Routine tasks, launcher close-out and new agent
sessions do not invoke them or require their outputs. The shared
[completion policy](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)
governs task progression even when old reports have expired.

`tools/read-only evidence-links --plan 'docs/Plan.md' --declarations 'declarations.json'`
provides read-only semantic validation and a finite destination-change preview.
The declaration file is bounded regular UTF-8 JSON with exactly `schema:
"onpc-evidence-documents"`, `version: 1`, and `documents` (at most 256 explicit
document declarations under the [document evidence contract](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery)).
It uses authenticated plan/runner readers, never executes link text, scans the
repository, starts a launcher or writes documents. Exit 0 returns JSON previews;
exit 2 refuses malformed, unavailable, unsafe or mismatched evidence. Mutation
has no command-line switch: an authorized owner uses the separate apply API.
Selected-reference refusals return finite JSON diagnostics with their condition,
document/line, opaque expected/actual identities and a supported recovery action.
They exclude private claim text and raw reader errors. Malformed requests retain
the generic refusal. Role-aware lifecycle policy is owned by the
[execution-plan contract](Execution-Plans.md#accepted-evidence-lifetime-and-historical-recovery);
the read-only preview does not grant an advisory or mutation authority.

The [rule matching contract](https://learn.chatgpt.com/docs/agent-configuration/rules#understand-rule-fields)
matches literal argument prefixes; the strictest decision wins.
`match`/`not_match` examples test rules, not runtime arguments.

`tools/read-only evidence-inventory --plan 'docs/Plan.md'`
inspects tracked Markdown names from Git and their bounded legacy references.
Repeat `--catalogue 'checkout-relative.md'` to register a finite local Markdown
catalogue, including an untracked handoff; repeat `--owner-plan 'docs/Other.md'`
to inspect another explicitly selected plan's authenticated accepted snapshots.
It never reads a live checkpoint, starts a controller, edits documents, operates
a VM or renews acceptance. Source/archive scopes close before the report is
retained through the shared allocator in the normal standalone-report ring.
Exit 0 prints the private report path, content digest, classification counts and
typed owner-source findings. Exit 2 refuses an invalid or oversized inspection.
Findings inside a completed report describe unresolved inputs, not a passing
reference or recovered acceptance. There is no output-path or mutation option.

The report is bounded to 2048 documents, 32 MiB of document bytes, 8192
occurrences and 8 MiB of metadata. It contains document/use-site offsets, original
document/reference/claim digests, owner-supplied roles/context when available,
verified candidate digests, typed availability/refusal and pending/resolved
dispositions. It copies no claim prose, transcript or report contents. Missing
owner context stays pending even for a present path or an authenticated legacy
archive candidate. Examples and mutable locator/journal navigation are inert;
neither receives evidence authority. E10's revision/role policy and authenticated
member resolver remain the sole owners of semantic decisions. The inventory is
revalidated migration input for E12/E13, not a database, checkpoint or authority.
Each occurrence also carries non-executable `recovery` guidance: an action,
outstanding verification prerequisites and, for a protected missing source, a
pending historical-disclosure proposal. Its containing document/reference/claim
digests and offsets bind that proposal to the original occurrence. Unknown
consumer context or active relevance stays null; a surviving file candidate
does not fill it. Proposal prerequisites require exact completed-row links,
verified retained accepted completion, inactive controller baselines and retained
developer authorization before the existing controller-owned recovery can apply.
These prerequisites are not claims that those records exist or are absent.
The inventory neither generates an executable request with guessed values nor
requests product acceptance; access and identity refusals retain their distinct
supported recovery actions.

## Category coverage and future additions

Setup authorization is separate from runtime test authorization. The installed
`/usr/local/libexec/onpc-setup` accepts exactly one of `dependencies`,
`codex-rules`, `test-tools`, `graphical-policy`, `ppa-build-tools`, `rpm-build-tools`, `vm-host`,
`headless-dependencies`, `headless-tools`, `replace-missing-baseline`, `prepare-vm`,
`backupvm` or `restorevm`. The two headless operations select only the existing
dependency/helper installers with the fixed internal `--headless` argument.
The public entry point is `./setup.sh --server`; internal operation names and
arguments stay stable for compatibility with already installed dispatchers.
The disaster recovery operations accept only a registered `--vm` queue selector
(default `all`), never caller-supplied archive, domain XML or disk paths. They
use `backup_root` from the trusted registry and the existing setup authorization;
see [VM disaster recovery](../tests/integration/Environment.md#vm-disaster-recovery).
Only `prepare-vm`
requires the fixed arguments `--mode auto` or `--mode manual`, optionally
followed by `--y`; arbitrary paths
and other arguments are refused. Its
dedicated Polkit action defaults to denial and grants active local members
of the host administrator group (`sudo` on Ubuntu, `wheel` on Fedora), or the
explicitly configured headless administrator described in [one-time setup](#one-time-setup).
`setup.sh` and `tools/prepare-vm` check this authorization without
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
| App fixtures | `tools/run-tests fixtures build` / `verify 'ARTIFACTS'`; add `--kind native-runtime --target ubuntu\|fedora` for immutable target bundles | Fixed builders; builds generate an empty private output directory. The [frozen bundle contract](../tests/support/README.md#frozen-native-fixture-bundles) owns finite targets, input verification and producer lifetime. |
| Execution-owned native fixtures | `tools/run-tests fixtures prepare --kind native-runtime --target ubuntu\|fedora` | Verified reuse within the existing retained execution, or a separately registered copy of verified producer output; immutable selection and authenticated read-only handoff. No VM or product operation. |
| Package/fixture artifacts and reproducibility | `tools/run-tests artifacts build` / `verify 'ARTIFACTS'` / `compare 'FIRST' 'SECOND'` | Fixed builder; explicit existing project artifact inputs |
| Reusable package/fixture preparation | `tools/run-tests artifacts prepare` | Content-qualified reuse or a fresh build; new private output registered in bounded run retention. No VM or installed product changes. |
| Named qualification inputs | `tools/run-tests system --vm NAME check_parent_setup` | Explicit qualifications using `named_input()` automatically select current source-keyed inputs and prepare absent bundles before privileged dispatch. Same unprivileged builder and retention; exclusive creation, no overwrite. A legacy fixed-name bundle is never selected. Shared launcher coverage follows the [test scope mandate](Mandates/Test-Scope-Mandate.md). |
| Privileged harness/graphical checks | `tools/run-tests system --vm NAME check_future_feature` | Direct `tests/integration/check_[a-z][a-z0-9_]*.py`; no script options |
| Host worker containment | `tools/run-tests graphical-worker` | Isolated host fixtures; included in `host`, excluded from `system` and `vm` |
| Host package notices | `tools/run-tests package-notice` | Native APT/dpkg Ubuntu/Debian host fixtures; included in `host`, excluded from `system` and `vm` |
| Installed identity, authorization, enforcement, time, activation, migration, removal and reinstall | `tools/run-tests system --vm NAME --artifacts 'ARTIFACTS' --area authorization --test 'case[param]'` | Existing guarded VM controller; future registered areas/cases need no new rule |
| Graphical journeys and harness scenarios | `tools/run-tests e2e --vm NAME` / `tools/run-tests e2e --vm NAME --id 1,3,4` / `tools/run-tests e2e --vm NAME --list` | Defaults to every runnable E2E case, reporting pending exclusions; no other test categories are dispatched. Missing artifacts are built automatically; `--artifacts 'ARTIFACTS'` reuses verified inputs. Explicit pending/invalid IDs refuse before privilege checks. Serial owned recovery remains mandatory; no prerequisite test suite runs. See [commands and prerequisites](../tests/e2e/README.md#run-e2e-scenarios). |
| Asset-transfer runner qualification | `tools/run-tests e2e --vm NAME --qualify-transfer --artifacts 'ARTIFACTS'` | Guarded diagnostic attempt with live ownership checks; no scenario/list selector or product installation; pending customer dispatch stays closed |
| Authenticated installation qualification | `tools/run-tests e2e --vm NAME --qualify-install --artifacts 'ARTIFACTS'` | Fixed package installation through fixture-authenticated serial input; same guarded lease, private capture and owned recovery. No scenario/list selector; diagnostic qualification supplies no complete-scenario acceptance. Current bindings belong to the [scenario inventory](../tests/e2e/scenarios.json). |
| Established regressions | `make test-all VM=NAME` / `tools/run-tests all --vm NAME` / `tools/run-tests --vm NAME` | All established suites and ready E2E variants, automatic discovery, streaming report, owned cancellation; no selectors. With only `--vm NAME`, starts `all` when idle; [reconnection](../tests/README.md#aggregate-execution-and-reconnection) retains the original canonical selection. |
| Scripted test repair | `tools/fix-tests [--vm NAME] [CATEGORY ...] [--model MODEL] [--effort EFFORT] [--rounds X] [--tasks N]` / `tools/fix-tests --vm NAME --stop` | Granular pass only by default; --rounds X adds X-1 verification rounds; explicit selectors remain fixed. The [repair policy](../tests/README.md#scripted-repair-loop) owns GPT-6.1 Sol Medium → High → xHigh → Max escalation, with Low → Medium → High → xHigh for unit failures (including mixed/aggregate runs), five sessions per case/VM including answered blockers, and bounded diagnostic changes handed to launcher-owned execution. The launcher commits and pushes each repair's owned paths after confirming its specific case passed, before another repair; Git failures retain close-out for restart. Fresh serial Standard-speed sessions preserve stronger effort overrides; other models are refused and final-tier stalls may stop early. Different-case/preparation interruptions leave verification unknown without an exact runner-owned case pass. Existing sandbox/rules and owned cleanup apply; no automatic setup or authority expansion. |
| Execution plans | `tools/execute-plan PATH [--tasks N] [--stop] [--check]` | The [shared plan contract](Execution-Plans.md) owns format, task budgets and safe resumption. The task limit defaults to zero. Zero/negative task limits mean all remaining; oversized limits warn and finish with the queue. Each task owns its checks. The driver completes owned cleanup and Git close-out, then advances to the next unchecked row without collecting archives or rechecking old reports; `--check` makes no Git changes. Ownership, permissions and operation-specific mandates apply. |
| Complete host category | `tools/run-tests host [--continue-on-errors]` | All host work, including publishing, two fresh builds and comparison, in the aggregate's four branches; no VM discovery, authorization or execution |
| Complete VM category | `tools/run-tests vm [--vm NAME] [--continue-on-errors]` | System lifecycle, registered standalone checks and ready E2E coverage; required inputs are prepared automatically; independent host runs may overlap |
| Combined complete categories | `tools/run-tests host vm --vm NAME` | Equals `all`; `vm` expands to `system e2e`; any subset/order is accepted, scheduled host first, then sequential system and E2E; one report and shared package inputs; combined runs reserve both scope locks |
| Host compatibility alias | `tools/run-tests host-builds [--serial-builds] [--continue-on-errors]` | Same scope as `host`; `--serial-builds` retains publishing/builds after the host join for a scheduling comparison |
| Local publishing checks | `tools/run-tests publish` | Independently scheduled `publish-deb` and `publish-rpm` jobs, also selectable alone and included in host/test-all/test-all-verify; no publication |
| Future fast suite | `tools/run-tests fast --component broker --type contract` | Fixed `test-fast` target; refuses while unfinished |

For package builds, agents and automation use `tools/build_package.py` directly
(queued by default), or existing queued build APIs/test launchers. The local
package Make targets are human-only wrappers that skip disk admission; do not
invoke them from tools. The script performs the same version consistency check
and accepts `--format`, `--architecture` and `--rpm-release` selections.
Its executable grant is included in the tracked tools inventory.
The maintained rules forbid direct `make build`, `make updateversion`,
`make build-rpm`, `make srpm` and `make rpm-source` requests, overriding older
allows. These prefix rules protect those command shapes, not arbitrary Make
options or commands hidden inside programs; agents must not route around them.

Routine `make check`, `make check-release-version`, `make check-unit`,
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
prompt. After changing tracked rules, restart
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

Admitted shared cleanup-safety regressions remain in explicit unit/host/all
selections. Apply the [test scope mandate](Mandates/Test-Scope-Mandate.md) to
changed dangerous cleanup or ownership boundaries. No runtime passing-test receipt substitutes
for live ownership checks.
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
guest after renumbering. **ONPC: Watch** observes all registered
VMs; viewing does not authorize VM mutation.

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
| `tools/test-vm --vm NAME reproduce-suspend-active-grant` | Replay the shared real grant-only profile, original child activity, suspend/wake and legitimate guarded unlock, then read the child desktop through the same bound observer without advancing the journey. Close the worker and retain the owned child scene for inspection followed by `stop`; no customer acceptance credit. |
| `tools/test-vm --vm NAME reproduce-suspend-expired-grant` | Replay the shared real grant-only profile, original child activity and sleep across the original deadline. Stop at the first post-wake lock-surface read, close the worker and retain the same locked child for guarded `exec` diagnosis followed by `stop`; no customer acceptance credit. |
| `tools/test-vm --vm NAME exec [--timeout SECONDS] -- COMMAND [ARG ...]` | Execute as guest root in the current owned online app-snapshot maintenance instance; reuse saved private credentials, strict SSH host-key and guest identity checks, shared observation and the exclusive lease; preserve guest state and return its command status |
| `tools/disable-extension --vm NAME` | Explicit development-only extension isolation in that same owned running maintenance instance, through `test-vm exec`; deploy an unshipped launcher/override, restart the broker and disable eligible children's extensions. No VM boot, restore, snapshot capture or production package changes; [usage and lifetime](../tests/support/README.md#development-only-extension-isolation). |
| `tools/test-vm --vm NAME reproduce-gdm-denial` | Diagnostic-only replay of the shared fresh-child zero-time journey through its bounded Cancel sequence; close the graphical worker and retain the owned online guest before final account-list observation, for `exec` probes followed by `stop`. No acceptance credit. |
| `tools/test-vm --vm NAME reproduce-remove-selected` | Replay case 180's shared spare-child setup, saved choices and single guarded removal; observe Parent's automatic Riley fallback once without advancing that boundary, close the worker and retain Parent for guarded `exec` diagnosis followed by `stop`. Requires the maintained named package input; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-policy-legend` | Replay the shared Jordan policy-legend journey through independent App Limits entry and stop before expansion. Close the worker and retain Parent for guarded `exec` diagnosis followed by `stop`; requires the maintained named package and native fixture input, with no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-kiosk-preferences` | Replay the shared prepared kiosk request up to the Preferences restriction stage, run its public operation once as a private diagnostic, then close the graphical worker and retain the owned online guest for `exec` probes followed by `stop`. Keep success or refusal separate from acceptance; no restriction stage advances and no acceptance credit is supplied. |
| `tools/test-vm --vm NAME reproduce-station-shortcuts` | Replay the shared shortcut qualification through ordinary overview and app-grid use/closure, then retain the ordinary desktop immediately after its single Alt+F2 input, before reading that result. Close the worker and retain the owned guest for `exec` diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-baseline-app-effects` | Replay the shared baseline time/app setup, genuine grant and child entry, then make one diagnostic Allowed A command-launch observation at the unanswered worker boundary. Close the worker and retain the owned child scene for `exec` probes followed by `stop`; never replay an uncertain launch. Retain its SSH exit status on failure; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-baseline-restoration` | On owned Ubuntu/Fedora online app-snapshot maintenance, replay the complete shared C04j baseline history up to the unanswered `restore-saved` request, then observe `parent-save-disabled` once. Freeze target-specific selected fixtures under the VM reservation and retained host owner; stage package-only installed helpers, authenticate the live snapshot and rebind its key/marker to this maintenance run without restoring it or resetting its clock. Publish maintenance credentials only after fresh transport and account verification, then run the baseline caller's qualified native/activity preparation and readiness checks. This fixed binding alone has a 1800-second worker deadline. Close the worker and callback and retain the Parent scene for guarded `exec` diagnosis followed by `stop`; requires the maintained fixture-bound named package input and supplies no acceptance credit. |
| `tools/test-vm --vm NAME probe-kiosk-latency [SAMPLES [COLD]]` | Measure ten public station-entry/Cancel cycles by default (optional count 1–10) from the greeter in an owned online app-snapshot guest. Optional `COLD=1` reboots the owned guest before each sample; `0` preserves the boot. Reuse the guarded entry, form and greeter observations; retain timings through recovery storage. No reset, installation, secret input or acceptance claim; finish with `stop`. See [timing limits](../tests/e2e/README.md#kiosk-transition-timing). |
| `tools/test-vm --vm NAME probe-kiosk-prompt-latency [SAMPLES [COLD]]` | Prepare the shared public request flow up to its first native prompt, including fixture Parent sign-in, then measure ten Request/prompt/Cancel cycles (optional count 1–10), keeping complete prompt ownership and unchanged-form checks. Optional `COLD=1` reboots before each measured sample. The measured approval prompts receive no password. No reset or acceptance claim; retain private timing evidence and finish with `stop`. See [timing limits](../tests/e2e/README.md#kiosk-transition-timing). |
| `tools/test-vm --vm NAME reproduce-kiosk-approval` | Replay the shared kiosk approval history through the real password prompt, then close the graphical worker before challenge qualification or password input. Retain the owned online guest for identity/mount probes followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME probe-kiosk-approval` | In the exact retained owned `Request denied` form, independently check the prepared child, approver, 75-second duration and soft-app choice, refresh the public custom entry from `1.25` to equivalent `1.250` and back with guarded readbacks, then invoke the shared public Request action once and retain the native prompt before password input. Retain bounded agent/Glycin journal evidence in the same owned probe allocation, with capture status separate from the observer result. No setup, backend mutation, secret provisioning or acceptance credit; finish with `stop`. |
| `tools/test-vm --vm NAME reproduce-lock-denial` / `reproduce-retained-entry` | Replay the shared child denial or retained two-child history in the same owned maintenance envelope, stopping before the native restriction read or restricted curtain read respectively. Close the worker and retain the guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-countdown-minutes` | Replay the shared four-minute daily-only preparation and fresh child entry, stopping before minute progression. Retain a fresh public countdown read and the owned guest for engineering probes followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-natural-expiry` | Replay the shared four-minute daily-only preparation and native activity, stopping immediately before the measured natural-expiry observation. Retain the child's desktop for engineering probes followed by `stop`; no acceptance credit. Uses the qualification's attempt-owned activity fixtures and maintained package input. |
| `tools/test-vm --vm NAME reproduce-countdown-resume` | Replay the qualified child lock/unlock history with guarded 20-second active and 70-second locked intervals. Retain public countdown reads before locking and after authenticated return for engineering diagnosis, followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-retained-unlock` | Replay the shared retained-child unlock history, including native activity submission/capture, locking, greeter return and guarded GDM authentication. Before the first retained GDM recipient proof, start [bounded SSH capture](../tests/integration/retained_unlock_capture.py) in the pinned inactive child session and require subscription readiness. Read a bounded baseline of roles/states, then capture ScreenSaver/logind lock transitions and public Shell modal/showing/visible state events for 45 seconds, capped at 512 records; never read password names/text. Distinguish live roles, historical baseline roles for retired objects, and unresolved role reads. Require the capture window to span the final recipient proof and desktop boundary. Capture has a separate command owner, joins after worker shutdown and retains `unlock-transitions.json` and its result; it does not delay the immediate desktop check. At the `unlock-desktop` request, run the shared desktop check through its diagnostic-only alias before closing the worker. A prompt refusal retains fixed public categories from the same snapshot and ScreenSaver lock state. At most three further read-only snapshots start within five seconds under the existing observer/transport limits; the first refusal remains failed. Retain the owned guest for diagnosis followed by `stop`. No journey stage advances at that boundary. Requires the maintained fixture-bound named input; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-fullscreen-return` | Replay case 127's shared zero-time denial, real ten-minute approval, fullscreen game and natural expiry, then twenty-minute recovery approval and guarded GDM authentication. Stop before the recovery countdown read, close the worker and retain the owned child scene for `exec` diagnosis followed by `stop`. Uses the maintained named package/game input and an 1800-second worker budget; no acceptance credit. |
| `tools/test-vm --vm NAME probe-fullscreen-return` | Independently read the recovered Jordan game activity, then that child's public countdown in the owned retained scene. Retain each observation or refusal without input or acceptance credit; finish with `stop`. |
| `tools/test-vm --vm NAME reproduce-transfer-refusal` / `probe-transfer-refusal` | Replay the shared overlay-to-kiosk history up to Riley's wrong-surface refusal, or read that refusal in the retained child session. Keep the guest for guarded `exec` diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME reproduce-remembered-return` / `probe-remembered-return` | Replay case 58 through Jordan's return credential and retain a desktop read at that boundary before worker shutdown, or read the retained child session again. Keep the guest for guarded `exec` diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME repeat-remembered-return` | From that retained Jordan scene, replay Riley's retained transfer and Jordan's return using the same helpers, retaining the desktop read and guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME enter-remembered-return` | Start a new guarded Jordan return challenge from the owned reproduced greeter, retaining the desktop read and guest for diagnosis followed by `stop`; no acceptance credit. |
| `tools/test-vm --vm NAME probe-lock-curtain` | Run only the shared read-only child curtain observer in the current owned maintenance scene, retaining guarded command evidence; never reveal, authenticate or unlock. |
| `tools/test-vm --vm NAME probe-lock-time-denial` | Pin an already visible native child time restriction and independently read the same denial in the same boot through the shared observer. Retain read-only evidence; never reveal, enter credentials or unlock. |
| `tools/test-vm --vm NAME rename --new-name LABEL` | Rename the idle, powered-off pinned UUID, preserve snapshots and disks, and move its private provenance directory; refuses existing destination state and unfinished controllers |
| `tools/test-vm --vm NAME rename-disk` | Rename the idle pinned guest's single QCOW2 image to `NAME.qcow2` in its existing directory; update domain/internal-snapshot references and provenance, preserving bytes and inode; refuses overlays, shared disks, destination collisions and unfinished controllers |
| `tools/test-vm --vm NAME start` | Acquire the shared lease, validate provenance/disks/snapshot, restore the outer baseline, record and boot an isolated maintenance attempt |
| `tools/test-vm --vm NAME start --fixture-maintenance` | Start dedicated product-free Ubuntu/Fedora maintenance for the fixed `trusted-hard` subset; see [idle fixture maintenance](../tests/integration/README.md#idle-fixture-maintenance-refresh) |
| `tools/test-vm --vm NAME sync-fixtures` | Build/select current native input in that same host owner and explicitly verify or replace the idle maintenance generation; refuse uncertain ownership, sessions and changed subsets |
| `tools/test-vm --vm NAME reboot` | Request reboot over the same recorded instance's guarded SSH transport and verify its new boot; preserve guest state |
| `tools/test-vm --vm NAME send-key 28` | Send 1–16 numeric Linux keycodes (1–255) to that instance; no shell or host command |
| `tools/test-vm --vm NAME screenshot` | Capture the owned running guest through the legacy `/tmp/onpc-vm-screen-*` allocation; migration to [shared storage](Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes) remains required. This is separate from the caller-owned PNG export exception. |
| `tools/test-vm --vm NAME stop` | Stop only that recorded maintenance instance, verify/restore the outer baseline and original domain configuration, leave it off; interrupted record cleanup after completion requires exact off-state, configuration, snapshot and guest audits before retiring matching records |
| `tools/test-vm --vm NAME reset` | Restore the accepted outer baseline while idle, leaving the VM off |
| `tools/test-vm --vm NAME recover-online ID` | After explicit authorization of the inspected instance, restore its baseline and leave it off. A fully recorded maintenance instance requires its exact saved owner, run and instance, even if SSH credentials are unavailable; an interrupted online start retains matching private snapshot and isolation proofs. |

`tools/test-vm --vm NAME reproduce-grant-logout` replays case 9's shared
Parent saves, real 20-minute approval, fresh Jordan entry and native app checks
in the owned online maintenance guest. At the first grant-active logout it
submits the shared operation once while the worker remains active, records
bounded session diagnostics without advancing that stage, then closes the
worker and retains the resulting scene for guarded `exec` diagnosis followed
by `stop`. The diagnostic also samples guest memory, swap counters and host VM
RSS throughout its replay. It requires the maintained fixture-bound named
package input and supplies no acceptance credit.

Every mutation shares the runner's nonblocking exclusive lock. Reopened
maintenance operations require a matching root-private ownership record,
run/domain instance, original configuration, baseline digest and snapshot digest.
Other active controllers and replaced identities are refused. No new domain,
snapshot, clone, overlay, arbitrary XML, host-device attachment or general
host shell is exposed. Guest root commands have no program allowlist; shell
programs and interpreters execute only inside the isolated guest. No reset occurs
between reboot/input/probe steps. Probing neither starts nor restores a guest,
rotates its keys nor adjusts its clock. It requires the current online app
snapshot's private credential record, or the dedicated baseline-maintenance
transport, and the existing maintenance ownership journal; manually started
guests and active test controllers are refused.
For lightweight diagnostics during an active test, use
`tools/test-vm --vm NAME probe memory` instead. The installed helper authenticates
the requester to the active owner's fixed read-only probe endpoint without
acquiring another checkout. See the [VM mandate](Mandates/VM-Mandate.MD#owned-maintenance-and-execution)
for the diagnostic bounds and lifecycle contract. This does not enable arbitrary
guest commands during tests.
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
current configured IDs and names. Probing eligible entries in `config/environment.json`
has standing user authorization; both VM and host must have `enabled: "true"`;
do not request command approval or developer confirmation. The installed
test-runner Polkit rule grants the active local administrator automatically,
with the designated headless account additionally permitted by the explicit
[headless grant](#one-time-setup). Unavailable authorization fails noninteractively without a dialog.
Do not add selector-specific or host-shell
grants. Keep the host invocation a simple literal command: complex embedded
quoting can prevent Codex's shell parser from extracting the launcher prefix.
For large guest scripts or text payloads, pass a shell-quoted literal encoded
argument and decode it inside the guest rather than embedding multiline source
or shell quote concatenations. Encoding changes transport only; guest identity,
ownership, observation and authorization checks still apply. A rules refresh
does not change that parser boundary or reload the current Codex process.
For example, a Python probe uses `tools/test-vm --vm NAME exec -- python3 -I -c
'import base64,sys; exec(base64.b64decode(sys.argv[1]))' 'ENCODED_SOURCE'`
as one literal command, with the complete reviewed source encoded in the final
argument. If a complex inline invocation reports an unsafe helper while simple
commands through the same launcher work, correct the transport shape first.
Do not reinstall the helper or request a new approval to repair shell parsing.
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
entry's `disk_anchor` in `config/environment.json` immediately after success;
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
`system check_graphical_recovery` remains the separate narrow recovery
route for an interrupted graphical runner, under its recorded identity checks.
`tools/run-tests` invokes `system check_test_recovery` automatically for
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
`processes` includes resident memory (RSS) and proportional resident memory
(PSS), both in KiB, alongside process identity.
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
override removed. Restart Codex after tracked project rule changes. Refresh host
read policies through `./setup.sh --test-tools-only` before restarting Codex.

Ordinary `rg -n`, `rg --files` and `sed -n` reads are explicitly allowed machine-wide across
all paths. Project prompt rules must not blanket-match `rg` or `sed`, since
that overrides the global allow. Prefix rules do not validate trailing options;
use these direct allowances, including `curl -fsSL`, only for trusted reads and
the validated reader for untrusted arguments. The curl prefix can also match
trailing upload, custom-request or output options; the allowance does not
authorize those operations. Preserve existing saved reader allowances for
`sort`, `uniq`, `head`, `tail`, `cut` and `wc`; project rules must not override
them or duplicate them. Ordinary file-discovery/filter pipelines are authorized
across paths, glob filters, sorting options and line counts, for example:

```sh
rg --files 'output/test-runs/host/reports' --glob 'category-*.log' | sort | tail -n '3'
```

These prefix grants do not validate trailing arguments: output-file options
still match saved `sort`/`uniq` allows, but this authorization covers reads only.
Use `tools/read-only` for untrusted arguments or argument-confined filtering.
`gzip` and `wget` retain their project prompt overrides.
Use quoted ripgrep `--glob '*pattern*'` options instead of
unquoted shell wildcards: Codex can classify shell expansion as an unsplit shell
invocation, which the direct executable rule does not cover. Never grant a
generic shell to solve that parsing limitation.

### Source discovery before reads

Use exact paths supplied by current instructions, resolved document links or
earlier successful checkout reads. For any other source or test filename,
discover the actual path before passing it to a content reader or search.
Do not derive `test_<module>.py` or wrapper test names from production modules,
launcher names, task titles or memory. Existing observed paths can be reused;
there is no need to list them again before every read.

Search a known directory with a quoted filename filter when the name is uncertain:

```sh
rg --files 'tests/unit' --glob '*plan*'
tools/read-only files 'tools'
```

Then read/search only the returned literal paths. Filename filters may match
nothing; that is a discovery result, not proof that a fixture or export is
missing. Check the owning contract before treating a planned test as an existing
file or a missing source file as a generated input. Resolve stale references
through the containing directory and relevant symbols rather than trying more
guessed filenames. Report a genuinely required missing source as unresolved;
do not create placeholders, suppress errors or broaden the lookup silently.

If a batched content read/search reports any missing operand, its other output
does not establish a complete lookup. Discover the correct paths and rerun the
affected lookup before drawing conclusions from it.

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
a newly written test is harmless. In particular, privileged system checks
remain trusted root code. Review changes to helpers, tests and rules before
running code from an untrusted branch. Ordinary tests, known operations and
new names within the documented contracts need no individual approval; new
privileged capabilities need validation and regression coverage in a maintained
helper, not a broad shell/interpreter grant.

Absolute guarantees of no prompt are not possible: missing setup, callers outside
the configured desktop/headless grant, sandbox denials, organization-managed rules and runtime policy
changes can override local grants. The goal is repeatable noninteractive
execution within the installed, validated scope, with explicit refusal outside
it. Codex and Polkit are separate controls. See the
[official Codex rules documentation](https://learn.chatgpt.com/docs/agent-configuration/rules)
for prefix matching, shell parsing, trust, startup loading and the precedence of
restrictive rules.
