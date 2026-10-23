# Child disables the extension

This proposed design closes the missing application-policy reconciliation trigger
when a child disables the extension. It is not implemented or installed-qualified.
It preserves the separate execution-policy acknowledgement limit; completing
this gate would not establish complete bypass resistance.

The [specification](../../Specification.md) owns customer behavior. Current
boundaries are in [Screen time](../Screen-Time.md),
[Application policy](../Applications.md#session-entry-reconciliation),
[Broker](../Broker.md#authorization-and-grant-transactions),
[Lifecycle](../Lifecycle.md) and the [threat model](../../Threat-Model.md).

## Required behavior

A child who lets a soft-app grant expire with the extension disabled must not
retain its app exception after entering the desktop using renewed daily time.
Every admitted managed-child graphical authentication must check time access,
reconcile policy, then check time/identity again before success. Required
preparation failure or uncertainty denies that attempt; extension state is
neither authorization nor policy.

| Authoritative grant | Required action |
| --- | --- |
| Nonzero, expired | Restore/verify complete hard and soft policy and derived native rules; stop matching child-owned apps and verify completion. |
| Current | Preserve live policy, including a stricter parent save after approval. |
| Zero duration | Preserve existing no-transition behavior while validating readiness. |
| Malformed/unavailable | Deny the attempt. |

Never reconstruct hard-only policy from a current grant, use remembered request
choices as authority, clear expired grants to suppress repeats, award time or
alter usage, allowance, duration or issuance. `LimitType == NONE` is not an
app-policy exemption. Natural grant expiry during uninterrupted permitted use
still does not immediately revoke apps.

## Authentication and native locking

The required order is successful configured authentication with every factor,
time check, privileged reconciliation, final time/identity check, PAM success,
then GDM login/unlock. GDM 50 performs an account check during reauthentication
but overrides failure for an existing session; an account/session-only gate
cannot protect unlock. See the [upstream worker](https://github.com/GNOME/gdm/blob/50.0/daemon/gdm-session-worker.c).

Success must never skip the gate, and failed/cancelled credentials must never
reach its mutations. A `required` password module continues after failure.
Generated-stack review must account for sufficient/done/reset, numeric jumps and
include/substack boundaries, preserving configured factors. `PAM_USER` alone
does not establish authentication. See [Linux-PAM control semantics](https://github.com/linux-pam/linux-pam/blob/v1.7.0/doc/man/pam.conf-syntax.xml).
Do not infer safe placement from Ubuntu profile priority or append a mutating
gate to Fedora's existing prepended block. Distribution patches need separate
generated-stack and real-libpam qualification.

Password, fingerprint, smartcard, passwordless, automatic/timed and remote
graphical routes, including unlock, must be protected or explicitly disallowed
through maintained integration. An enabled bypass remains a blocker; record
switch/resume paths that do not authenticate. Fresh login needs no existing Shell.

Native exhaustion locking with the extension disabled must be demonstrated.
[GNOME's native path](https://github.com/GNOME/gnome-shell/blob/50.0/js/misc/timeLimitsManager.js)
depends on locking being available. An unlocked child never reaches PAM; disabled
locking, alternative desktops and other own-UID Shell tampering remain outside
this gate's solution.

Preserve root/admin/kiosk recovery and kiosk confinement using current trusted
roles and distro mappings. Unknown/disagreeing identity is not an exemption.
Keep this reconciliation out of sudo, systemd-user, terminal/SSH and unrelated
authentication; preserve ordinary account/runtime-cap behavior.

## Broker, concurrency and lifetime contract

The proposed additive root-only API is:

```text
PrepareSessionAccess(
    uint32 target_uid,
    string expected_username,
    uint64 deadline_monotonic_usec
) -> string outcome
```

Successful outcomes are exactly `reconciled`, `current-grant` and
`no-recorded-grant`, never reusable authorization. Old/missing brokers, unknown
outcomes, malformed replies, service loss and structured errors deny entry.
Authorize bus UID 0 before bounded worker allocation, with service/core checks.

The fixed root-owned PAM helper uses a constructed environment with trusted
service/identity, no inherited search path, password or child-supplied authority.
Broker NSS/AccountsService identity and eligibility must agree and be revalidated
before writes, signals and success. UID/username alone cannot detect identical
identifier reuse. Logs exclude identity, credentials and raw backend errors.

Share an internal reconciler with `Broker.prepare_own_session()`, preserving its
public API and separate authorization. Serialize all relevant policy writers,
including `SetParentControl`, with approval, revoke, saves and preparation under
one documented lock order. Busy returns temporary failure without waiting for
parent authentication. Never overwrite a newer grant with a stale snapshot.
External AccountsService/filesystem writers still require bounded revalidation;
an in-process lock cannot exclude arbitrary administrator changes.

Apply strict policy before signalling verified child-owned pidfd targets across
retained sessions. Verify exits and perform a bounded final rescan; respawn or
unverifiable ownership denies entry. Never signal a whole user/session or other
account. Reject omissions in the target's required live rules, including unmatched
warnings tied to that reconciliation; other accounts' isolated omissions are not
this child's failure. Aggregate activation/storage failure still denies.

The decision is final validated state under the transaction lock. Re-evaluate
expiry during work, then re-read time. Later expiry follows ordinary behavior;
PAM completion/compositor access are not atomic. Add neither grace time nor
unbounded retries to chase that interval.

One monotonic budget starts after credentials, before helper/backend startup:
initial targets are 20 seconds for preparation and 25 seconds through PAM return.
Pass an absolute deadline; broker caps it and rejects expiry. Bound bus/NSS,
connection, subprocess, lock and exit work without per-call/Flatpak budget resets.
PAM helper wait needs owned watchdog/reaping; constants alone do not prove bounds,
including suspend/resume.

Timeout/cancellation/caller loss denies entry and ignores late replies. Stop new
mutations once known, safely settle started effects and retain transaction
ownership until no worker can mutate. Client timeout is not remote cancellation.
Unsettled retries stay busy/denied; old workers must not write after broker restart.
Recovery reads authoritative partial state without cached success or mutation replay.
After termination begins, keep strict policy; closed apps cannot be restored.
Only confirmed exhaustion maps to `PAM_ACCT_EXPIRED`; preparation failure remains
distinct. New visible errors require all supported translations.

## Startup and assurance limits

Preserve startup extension reassertion and readiness. An unavailable broker denies
managed-child entry while retaining recovery exemptions. A healthy broker must
reconcile with the extension still disabled. Reboot, migration and policy failures
retain refusal. Decoupling UI health from enforcement readiness is separate work.

Current readback/compile/notification success is weaker than active-generation
acknowledgement; see [notification limits](../Applications.md#notification-recovery-and-acknowledgement-limit).
A representative blocked launch, sleep, log or canary cannot prove every admission.
Stronger claims require fresh forward/rollback/removal acknowledgement, stale/
partial/permissive/restarted-daemon handling and qualified backend routes.

## Acceptance boundary

Verify generated PAM flow, failed/cancelled/multifactor authentication, role recovery,
contention, malformed state/replies, rule omissions, termination/activation failures,
timeouts, caller loss/restart, replacement-grant races and owned retry on both
supported distributions. Host checks cannot replace installed route qualification.

The retained-session customer history keeps the extension disabled: approve a
short soft-app grant, open blocked and unrelated-user apps, let all time expire
naturally, observe native lock and zero-time denial, then authenticate with the
next day's allowance. Blocked retained apps must close, new blocked launches fail,
allowed apps work and the other user's app continues. Re-enabling the extension
or restoring an intermediate state invalidates this variant.

Fresh login separately verifies blocked launches after normal sign-out and grant
expiry; it cannot establish retained-app closure. Native, Snap and Flatpak routes
need their own scope. Customer observations prove results; engineering checks
prove pre-success ordering and injected failures. This acceptance closes the
entry trigger only, not the independent policy-generation assurance gap.
