# Child disables the extension: design and execution plan

Status: reviewed design and proposed assignments; nothing here is implemented
or installed-qualified. Begin with the design gates below. Implementation
assignments become ready only after their prerequisites pass. This plan closes
the missing reconciliation trigger; it retains the separate execution-policy
activation limitation and does not promise complete bypass resistance.

The [specification](../../Specification.md) owns customer behavior. Current
boundaries are in [Screen time](../Screen-Time.md),
[Application policy](../Applications.md#session-entry-reconciliation),
[Broker](../Broker.md#authorization-and-grant-transactions),
[Lifecycle](../Lifecycle.md) and the [threat model](../../Threat-Model.md).

## Required behavior

> A child disables the Oh No! extension, lets a grant that allowed soft apps
> expire, and later enters the desktop using renewed daily allowance. The
> previous grant's app permissions must not survive that entry.

Every admitted managed-child graphical authentication must confirm time access,
reconcile an expired nonzero grant, and check time again before reporting
success. Failure or uncertainty in required preparation denies that attempt.
The extension's state supplies neither authorization nor policy.

| Authoritative grant state | Required action |
| --- | --- |
| Nonzero, expired | Restore complete saved hard and soft blocks and derived execution policy; stop matching child-owned apps; verify completion. |
| Current | Preserve current live policy, including a stricter parent save after approval. |
| Zero duration | Preserve the existing no-transition behavior. |
| Malformed or unavailable grant/policy | Deny this attempt. |

Do not reconstruct hard-only policy merely because a grant is current. Do not
use the request form's remembered soft-app choice, clear expired grants to
suppress repeats, award time, or change usage, daily allowance, grant duration
or issuance time. App policy is independent of screen-time enablement;
`LimitType == NONE` is not an app-policy exemption.

This change does not introduce immediate app revocation at natural grant expiry.
Soft apps may remain available during uninterrupted use while daily time remains,
as described in the existing specification. The decision boundary below limits
the new guarantee.

## Authentication and native locking

Required order:

```text
Successful configured authentication, including all required factors
    -> time-access check
    -> privileged app-policy reconciliation
    -> final time-access and PAM-identity check
    -> PAM authentication success
    -> GDM completes login or unlock
```

GDM 50 calls `pam_acct_mgmt()` during reauthentication and then replaces its
result with success for an existing session. The issue is an ignored failure,
not an absent account check. An account-only or session-open hook cannot protect
unlock; failure must reach `pam_authenticate()`. See the
[upstream worker](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session-worker.c).
Qualify the installed distribution versions and patches separately.

PAM control flow must prove both that success cannot skip the gate and that
failed credentials cannot reach its mutations. A `required` password module
continues on failure, so placing the gate after it is insufficient. Audit
`sufficient`, `done`, numeric jumps, include/substack boundaries and `reset`;
preserve every configured authentication factor. `PAM_USER` alone does not
prove authentication. See [Linux-PAM semantics](https://github.com/linux-pam/linux-pam/blob/v1.7.0/doc/man/pam.conf-syntax.xml).

Do not append a mutating gate to Fedora's current
[prepended block](../../../packaging/fedora_pam.py), or infer Ubuntu control flow
from [profile priority](../../../data/pam-configs/oh-no-parent-control-session-limits).
Require exact generated-stack review and real libpam tests. Wrong or cancelled
credentials must exit before reconciliation. Cancellation after mutations start
denies entry but cannot restore applications already terminated.

Inventory password, fingerprint, smartcard, passwordless, automatic/timed and
remote graphical entry wherever admitted, including retained-session unlock.
A passwordless route must still execute the gate after its normal authorization.
Classify each route as protected, disallowed through maintained integration,
or an unresolved blocker. An enabled bypass cannot be made safe by labelling
it unsupported. Record session-switching/resume paths that do not authenticate.

GNOME Shell 50 has its own parental-controls lock path, but calls it only when
locking is available; see the [dispatcher](https://github.com/GNOME/gnome-shell/blob/50.0/js/misc/timeLimitsManager.js).
Native exhaustion locking with the extension disabled is a prerequisite for
the complete scenario, not a conclusion from this source inspection. A child
who remains on an unlocked desktop never reaches PAM. Disabled locking,
alternative desktops and other own-UID Shell tampering are not solved by this
entry gate; preserve their threat-model obligations.

Preserve root, administrator and kiosk recovery and kiosk confinement. Use
trusted current identities, the distro's administrator mapping and configured
kiosk identity; resolve disagreement between PAM and broker roles. Unknown
identity/role is not an exemption. Keep this new reconciliation out of `sudo`,
`systemd-user`, terminal/SSH and unrelated service authentication. Fresh login
requires no existing child session or Shell; retain its account checks and
graphical runtime-cap handling.

## Broker, concurrency and lifetime contract

Extend the [PAM module](../../../tools/pam_oh_no_parent_control.c) and
[helper](../../../tools/session_limit_check.py) with this proposed additive API:

```text
PrepareSessionAccess(
    uint32 target_uid,
    string expected_username,
    uint64 deadline_monotonic_usec
) -> string outcome
```

The closed successful outcomes are `reconciled`, `current-grant` and
`no-recorded-grant`. They describe a grant decision, not reusable authorization.
Unknown outcomes, malformed replies, an old broker without this method, service
loss and structured error replies deny the attempt.

Authorize only system-bus callers whose credentials resolve to UID 0, before
worker allocation, with service and core checks. Do not reuse the broader
administrator-or-root permission. The fixed root-owned helper receives PAM
identity/service through a constructed environment, never child-provided state,
inherited search paths, passwords or authentication tokens. The broker resolves
NSS and AccountsService, validates agreement and target eligibility, and
revalidates before writes, signals and success. UID plus username does not solve
deletion/recreation with identical identifiers. Never log these identifiers,
credentials or raw backend errors.

Reuse `Broker.prepare_own_session()` in
[core.py](../../../broker/oh_no_parent_control/core.py) through one internal
reconciler with separate admission validation and authorization. Preserve the
public `PrepareOwnSession` signature. Current and zero-duration outcomes must
still validate relevant policy and backend readiness.

Serialize with approval, revocation, app saves and other preparation. Add
`SetParentControl`, currently outside the shared transaction lock. Audit other
writers, preferences, AccountsService notifications and periodic policy rescans,
and document one lock order. A busy transaction returns temporary failure
without waiting for parent authentication. A replacement grant committed first
is preserved; reconciliation committed first may be followed by a new approval.
Never overwrite a newer transaction with a stale snapshot.

An in-process lock does not serialize external AccountsService writers or
mutable app files. Revalidate before success; disagreement denies or restarts
within the same budget. Do not claim protection against arbitrary concurrent
administrator changes.

Apply strict policy before stopping apps. Use existing verified process identities
and pidfds across the child's retained sessions; never kill a whole user/session
or another account's processes. Verify exits and perform a bounded rescan for
matching apps appearing during discovery/termination. Continued respawn or
unverifiable ownership denies the attempt; a termination count alone is not proof
that no matching app remains.

Reject renderer omissions affecting the target's required live blocks, including
unmatched live-rule warnings, using warnings tied to that reconciliation result.
Other accounts' isolated omissions are not this child's failure; aggregate
activation/storage failure still denies. Existing partial-enforcement success
must not silently become admission success.

The app-policy decision is the broker's final validated state under the transaction
lock. Re-evaluate if the grant expires during work; the helper then reads current
time state again. Expiry after that decision follows ordinary natural-expiry
behavior. Later parent transactions apply normally. PAM completion and compositor
access are not atomic: do not promise an instantaneous desktop barrier, add
grace time, or retry indefinitely to chase this interval.

Start one monotonic budget at post-credential gate entry, before helper/backend
startup. Initial qualification targets are 20 seconds for checks/reconciliation
and 25 seconds for PAM return including helper handling; interactive credential
entry is outside that budget. Pass the absolute work deadline using the same
host monotonic clock. The broker rejects expired deadlines and caps its own
maximum; the caller cannot extend it.

Bound connection, NSS, subprocess, bus-call, lock and process-exit operations.
Do not reset the full timeout per call or Flatpak instance. The C module's
blocking `waitpid()` needs a watchdog and owned helper cleanup/reaping.
Timeout constants alone do not prove a bound; qualify stalls and suspend/resume
semantics explicitly.

On timeout, cancellation or caller loss, PAM denies and ignores late replies.
Stop before new mutations when cancellation is known; safely settle effects
already in progress. Client timeout is not remote cancellation. Retain transaction
ownership until no worker can still mutate; unsettled work keeps retries
busy/denied. Bound worker admission before spawning, including the child-callable
path. On broker restart, old workers/subprocesses must not outlive their owner and
write after the replacement begins serving. Test recovery from partial changes.

Retry from authoritative state, without cached success or automatic mutation
replay. Once termination starts, keep strict policy; exited apps cannot be
restored. File restoration alone is not verified rollback. Only confirmed
exhaustion maps to `PAM_ACCT_EXPIRED`; preparation failure has a distinct error.
Translate any new customer-facing message into every supported language.

## Startup and assurance limits

Preserve existing startup extension reassertion and readiness. A broker that
cannot start denies managed-child entry; recovery exemptions must still work.
A healthy broker reconciles directly with the extension disabled, without
requiring re-enablement. Reboot-required, migration and execution-policy failures
continue to refuse operations. Separating enforcement readiness from UI health
is a different design change, not an implicit shortcut in this plan.

The current adapter checks AccountsService read-back and successful fapolicyd
compile/reload commands; it does not prove activation of the requested daemon
generation. Read the [acknowledgement limit](../Applications.md#notification-recovery-and-acknowledgement-limit)
and [generation-witness design gate](../Applications.md#generation-witness-design-gate).

This plan can close the missing-trigger gap under that existing contract.
Representative blocked launches, a sleep, a notification cache, a log message
or a single canary do not establish verified active policy on every admission.
A stronger claim depends on separately completing the generation-acknowledgement
design and failure qualification: stale/partial policy, daemon loss/restart,
permissive mode, rollback and supported backend routes. Do not assign that entire
unresolved project as a small subtask here or declare this scenario rock solid
after completing only the PAM gate.

## Assignment and integration rules

The following are proposed work-package IDs, not test selectors or completed
tasks. This product plan does not replace or advance the
[E2E execution queue](../../TestAutomation/E2E-Execution-Plan.md). New UI/E2E
capabilities and scenarios must use that queue's owners and the
[shared task contract](../../TestAutomation/E2E-Execution-Contracts.md#task-brief-contract);
a missing public route remains a prerequisite, not permission to invent a probe
inside customer acceptance.

One coordinator owns integration, interface decisions, this document and final
acceptance. Assign at most three workers alongside it. Every assignment must
include the contract sections above, exact prerequisites, exclusive write paths,
finite acceptance branches and the intended result. Read dependent modules,
but request coordinator reassignment before editing another worker's files.
Serialize shared-file changes; use isolated checkouts when needed and never
discard pre-existing work. Do not concurrently control the same VM.

Each implementation package includes its focused meaningful regressions.
Use the [test map](../../TestAutomation/README.md), [approval routes](../../Approval-Tools.md)
and applicable UI, VM and storage mandates. Inspect launcher help/list before
selecting tests; names below identify existing starting points, not promised
new selectors. Missing generated inputs use maintained preparation; missing
grants and behavior mismatches follow their owning contracts.

Ordinary assignments target one bounded operation and one work session.
The estimates below are planning ranges, not stop timers or authority to drop
validation. Before dispatch, split a package whose actual scope exceeds its
estimate. New UI/E2E tasks must meet their stricter 15–30 minute sizing contract;
package lifecycle, failure/recovery and natural calendar acceptance retain their
documented session exceptions.

Use GPT-6.1 Sol High for design, PAM, authorization, concurrency, ownership and
security review; use Sol Medium only for settled mechanical documentation or
test wiring. A worker returns changed paths, expected versus observed behavior,
exact checks and results/artifact pointers, remaining limitations and whether
its exit gate passed. The coordinator alone marks acceptance complete after
required integration and owned cleanup. No implementation is authorized by
this document-review session.

## Phase 0: settle platform and interface gates

| ID | Scope and owner | Prerequisites | Deliverable and exit gate | Estimate |
| --- | --- | --- | --- | --- |
| D-U | Ubuntu authentication audit; read-only source/registered VM investigation | Applicable VM and test contracts | Exact generated GDM stacks and package versions; every admitted route; credential-success-only insertion design; exemptions, account checks and runtime-cap preservation. | 30–60 min |
| D-F | Fedora authentication audit; same bounded work for Fedora 44 | Applicable VM and test contracts | Authselect/GDM route matrix, exact insertion design, admin-edit preservation and lifecycle constraints; no claim that Fedora is already qualified. | 30–60 min |
| D-LU | Ubuntu native-lock prerequisite | D-U | Observe native exhaustion with extension disabled, then zero-time denial and relevant resume/switch behavior through maintained routes; no re-enable masquerading as a pass. | 30–60 min, live qualification |
| D-LF | Fedora native-lock prerequisite | D-F | Same finite native-lock prerequisite on Fedora, with independent evidence. | 30–60 min, live qualification |
| D-I | Coordinator interface and control-flow review | D-U, D-F, D-LU, D-LF | Freeze exact PAM placements, protected/disallowed route list, role rules, API/reply/error/deadline schema, lock order, warning snapshot and worker settlement contract. Resolve mismatches; record any blocker here. | 30–45 min |

D-U and D-F may run in parallel on different registered targets. D-LU/D-LF use
independent owned attempts. D-I is a hard implementation gate: no unresolved
route may be silently skipped and no worker chooses a different wire protocol.
If a required supported API cannot satisfy the contract, return a design blocker;
do not compensate with private Shell state or weaker authentication.

## Phase 1: independent bounded components

All rows require D-I. Parallelize only disjoint write ownership; each worker
owns the named source and its focused tests for that assignment.

| ID | Exclusive change scope | Additional prerequisites | Acceptance | Estimate |
| --- | --- | --- | --- | --- |
| B-LOCK | `core.py` transaction entry/exit and `tests/unit/test_core.py` | None | Serialize SetParentControl; preserve existing toggle semantics; deterministic contention with approval/revoke/preparation; no lock release while owned work continues. | 30–60 min |
| A-DEADLINE | `adapters.py`, `execution_policy.py`, directly affected adapter/policy tests | None | Propagate frozen deadlines through admission's backend/activation calls; bounded stalls, unchanged normal callers, safe ownership on timeout. No generation-witness implementation. | 45–60 min |
| P-DEADLINE | `app_termination.py`, `tests/unit/test_app_termination.py` | None | One remaining budget across discovery, Flatpak operations and exit verification; no per-instance reset; verified UID/pidfd ownership preserved. | 30–60 min |
| P-RESCAN | Same termination files, after predecessor relinquishes ownership | P-DEADLINE | Bounded final rescan; race/respawn, disappearance, PID reuse and unrelated-user tests; exhaustion denies without broad signalling. | 30–45 min |
| H-CLIENT | `tools/session_limit_check.py`, `tests/unit/test_session_limit_check.py` | None | Frozen root call/reply/deadline protocol; both time checks; malformed/old/unavailable broker refusal; exemptions; fresh login without an existing session. | 30–60 min |
| H-PAM | `tools/pam_oh_no_parent_control.c`, directly affected real-libpam/helper-supervision tests | H-CLIENT | Fixed helper environment, bounded owned supervision/reaping, accurate PAM result mapping, no late success; preserve account runtime-cap behavior. | 45–60 min |

A-DEADLINE must split by adapter/activation boundary before dispatch if a
bounded cancellation/settlement primitive is missing. It must not expand into
the separate generation-witness project. New host/resource-affecting tests
receive the repository's parallelism and cleanup classification review.

## Phase 2: compose broker and distro integration

| ID | Exclusive change scope | Prerequisites | Acceptance | Estimate |
| --- | --- | --- | --- | --- |
| B-RECON | `core.py`, `adapters.py` warning-result binding, focused core/adapter tests | B-LOCK, A-DEADLINE, P-RESCAN | Shared reconciliation; expired/current/zero/malformed matrix; omissions on every success path; identity revalidation; preserve stricter/current policy; irreversible failures and expiry during work. | 45–60 min |
| B-SERVICE | `service.py`, private-D-Bus/service-contract tests | B-RECON | Root-only additive method and frozen schema; authorize before bounded worker allocation; nonroot rejection, busy, disconnect and late-completion behavior. Existing PrepareOwnSession signature retained. | 45–60 min |
| K-U | Shared PAM profile, `packaging/ubuntu.inc`, affected Ubuntu package/real-libpam tests | H-PAM | D-U's exact post-credential placement; valid/invalid/cancelled/multifactor paths; all admitted routes; exemptions; generated jumps and runtime-cap preservation. | 45–60 min |
| K-F | `packaging/fedora_pam.py`, `packaging/stage_distribution.py`, Fedora package/real-libpam tests | K-U, H-PAM | D-F's exact placement against the finalized shared profile; same credential/route checks; authselect local-edit refusal, preserved base features and reversible ownership. | 45–60 min |
| B-RECOVERY | Coordinator-assigned broker/service ownership paths and focused recovery tests | B-SERVICE, H-PAM | Caller timeout/cancellation keeps mutations serialized; restart settles old subprocesses before new writes; retry reads partial state; bounded bursts through both entry points. | 45–60 min |
| K-LIFECYCLE | `packaging/package_activation.py` and affected lifecycle/activation tests | K-F, B-RECOVERY | Mixed old/new component refusal, correct reboot/session-renewal classification, upgrade/removal/rollback and administrator edits; no forced child logout. | 45–60 min |

B-RECON begins only after both core and adapter owners finish. K-F follows K-U
because Fedora consumes the shared profile. B-RECOVERY follows B-SERVICE and
owns any necessary service-file edits; do not give both workers `service.py`
at once. The coordinator assigns exact recovery/lifecycle paths before dispatch
to avoid overlap. Shared diagnostics catalogue or translation changes receive
one explicitly assigned owner and all-language validation.

## Phase 3: integration, installed evidence and close-out

| ID | Scope | Prerequisites | Exit gate | Estimate |
| --- | --- | --- | --- | --- |
| I-REVIEW | Independent read-only security/concurrency review | All phase 2 | Trace credentials to admitted result, all success/denial branches, worker lifetime and policy warnings; findings resolved by original file owners with regression checks. | 45–60 min |
| I-BUILD | Coordinator integrated checks/build | I-REVIEW fixes complete | Lowest effective scoped regressions plus `make build` after final build-affecting edit; retain exact failures and missing prerequisites. | Runtime-dependent |
| S-U | Ubuntu installed failure/recovery qualification | I-BUILD | Backend down, busy, malformed reply/state, omissions, activation/termination failure, timeout/disconnect/restart, replacement-approval races, retry and root/admin/kiosk recovery. | 60–120 min, system-test exception |
| S-F | Fedora installed failure/recovery qualification | I-BUILD | Same explicit failure matrix on Fedora; distro route and lifecycle behavior independently verified. | 60–120 min, system-test exception |
| C-ENTRY | Complete finite entry/approval customer case per qualified distro/backend binding | Relevant S-U/S-F and qualified public operations | Manual lock/unlock after grant expiry with daily time left; fresh-login block; replacement grants with soft apps allowed/disallowed; stricter subsequent save; allowed-app and other-user continuity. | Case-dependent; split into existing recipe-owned cases |
| C-DAY | Complete natural next-day retained-session case per qualified binding | Relevant C-ENTRY and natural calendar eligibility | Central recipe below; continuous history and extension remains disabled. No injected clock or restored intermediate state substitutes for this pass. | Natural calendar exception |
| CLOSE | Coordinator documentation and acceptance reconciliation | All required installed/customer bindings | Specification and design agree; current GDM explanation corrected; evidence and remaining assurance limit recorded; no unpassed route/distro/backend called qualified. | 30–45 min |

S-U/S-F should be expanded before dispatch into the maintained runner's finite
cases when their matrix is not one existing system qualification; retain each
failure/recovery cycle intact. C-ENTRY/C-DAY are acceptance groups, not single
subagent implementation assignments: before dispatch, bind each row to one
existing numeric recipe/case or add the missing scoped prerequisite through the
owning E2E queue. Keep exact inputs, selectors, distro/backend scope and calendar
eligibility in those briefs. Never hand an agent “implement all acceptance.”

Customer steps for the central retained-session case:

1. Use finite daily allowance and approve a short grant allowing soft apps.
2. Open a representative soft-blocked app and another user's unrelated app.
3. Disable the extension and keep it disabled throughout the attempted bypass;
   observe that the countdown UI disappears.
4. Let all usable time expire naturally; observe native locking and verify that
   correct credentials cannot restore access while no time remains.
5. When the next day's allowance arrives, authenticate normally.
6. On entry, verify the retained blocked app is closed, supported new launches
   fail, an allowed app works and the other user's app remains usable.

Fresh login is separate: sign out normally while time remains, let the grant
expire, then log in with renewed daily time and verify blocked launches; it
cannot prove closure of a retained app. Qualify native, Snap and Flatpak
launch/termination routes separately, including supported launch races in
engineering tests. A restart that re-enables the extension invalidates the
disabled-extension variant. Customer observations establish public results;
engineering tests must establish pre-success ordering and injected failures.

Completion closes the entry-trigger work only after required evidence passes.
It does not close the independently owned generation-acknowledgement work or
establish a rock-solid enforcement guarantee. No package build, live acceptance
or product implementation is performed by this documentation review.
