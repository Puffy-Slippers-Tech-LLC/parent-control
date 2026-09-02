# Threat model and enforcement guarantees

## Scope and attacker

Oh No! Parent Control manages time and application policy for a local,
non-administrator child account.  The product's target security architecture
assigns policy decisions, authorization scoping, transactions, reconciliation,
and health reporting to the privileged system D-Bus broker.  Supported
operating-system services supply enforcement mechanisms behind that boundary.
Launcher visibility is not enforcement, and Malcontent alone is not a hard
security boundary.

The in-scope attacker is a managed child who can:

- use a terminal and run arbitrary code as their own UID;
- create, edit, and directly open desktop launchers;
- copy, rename, replace, hard-link, and execute files wherever their account
  has permission;
- construct arbitrary public system D-Bus calls, including calls which bypass
  all product front ends; and
- invoke product and backend Polkit actions and control the lifetime of their
  own processes and D-Bus connections.

Copying a binary, constructing a D-Bus call, and invoking a Polkit action are
therefore explicitly in scope.  None of those acts is proof of authorization.
A successful parent authentication may authorize only the child, duration,
end-of-day mode, and conditional-app choice displayed for that request.  It
must not confer a reusable or general AccountsService capability.

The attacker does **not** possess administrator credentials, cannot become
root, cannot modify the boot chain, and cannot exploit kernel vulnerabilities.
Compromised or voluntarily disclosed administrator credentials, existing root
access, offline disk modification, alternate boot media, boot-chain compromise,
firmware compromise, and kernel exploits are out of scope.  A flaw in an
integrated service that an ordinary user can exercise through an in-scope
operation is not excluded; H-40 specifically covers the Malcontent timer-storage
vulnerability.  Parent credentials remain an asset: the product must not
collect, persist, log, or expose credentials entered into the trusted Polkit
agent.

Remote administration, web filtering, GUI appearance, physical denial of
service, and replacement of Malcontent as a whole are outside this hardening
program.

## Assets and authorities

The authority column identifies the intended source of truth after the
hardening plan is complete.  It does not imply that all later-phase behavior is
already implemented.

| Asset | Authority | Required protection |
| --- | --- | --- |
| Daily allowance and enablement | Validated product preferences; projected to AccountsService | A child cannot change the configured limit or enablement state. |
| Runtime grants | AccountsService `ActiveExtension` | Only a complete, verified, parent-approved transaction can create or extend a grant. |
| Permanent app blocks | Validated product preferences | No access request, backend failure, or conditional relaxation may remove them. |
| Conditional app blocks | Validated product preferences | They relax only when that choice was displayed, authorized, and successfully committed with the grant. |
| Parent credentials | Parent and trusted Polkit authentication agent | Product processes never receive, store, log, or delegate the secret to a child. |
| Preference records | Root-owned `/var/lib/oh-no-parent-control/preferences/<uid>.json` | Front ends cannot access records directly; the broker schema-validates and atomically writes them. |
| Timer usage | `malcontent-timerd` | Only validated usage obtained through the authorized public parent interface contributes to grant calculation. |
| Generated execution rules | Broker-derived fapolicyd rule file | Rules are a verified, atomic projection of canonical app policy and apply only to the intended UID. |
| Audit logs | Root broker daily log writer | Logs are access-controlled, bounded, redacted, attributable to the correct component, and never writable directly by a child. |

Preferences are canonical only for configured product policy.  AccountsService
policy and fapolicyd rules are derived enforcement state,
`malcontent-timerd` is authoritative for measured usage, and AccountsService
`ActiveExtension` is authoritative for a live grant.  External or derived
state must never be imported silently into preferences.

## Trust boundaries

| Boundary | Trusted responsibility | Input or failure treated as untrusted |
| --- | --- | --- |
| Front ends -> system D-Bus | D-Bus supplies a unique live sender name; front ends only present choices and results. | Every method argument, UI-side calculation, label, claimed UID, and caller-controlled disconnection. |
| System D-Bus -> broker service | The broker resolves sender credentials, assigns caller role, validates targets, and returns redacted stable errors. | Calls which omit the UI, are reordered, repeated, malformed, or sent by arbitrary child code. |
| Broker service -> broker policy core | The service performs binding and error translation only; the core owns product policy and transaction order. | Adapter exceptions, stale objects, malformed backend values, and re-entrant/concurrent work. |
| Broker -> preference store | Broker validates the complete schema and uses secure atomic replacement. | Malformed records, symlinks, unsafe ownership or mode, future schemas, UID reuse, and interrupted writes. |
| Broker -> Polkit/authentication agent | The broker constructs the action details and Polkit authenticates the selected parent for that exact action. | Caller-selected identity, spoofed details, denial, cancellation, timeout, agent loss, retained authorization, and subject changes. |
| Broker -> AccountsService/Malcontent account API | Broker computes desired account state, orders writes, verifies read-back, and rolls back failure. | Service outage, partial writes, stale users, external changes, and malformed properties. |
| Broker -> Malcontent timer daemon and usage helper | `malcontent-timerd` measures usage; the identity-scoped helper performs only the documented parent query. | Busy/unavailable service, excessive or malformed output, wrong parent identity, corrupt storage, and clock/session anomalies. |
| PAM/GDM/GNOME Shell -> Malcontent | Only documented public login, session-limit, signal, and query integration is supported. | Startup races, crash/restart, missing services, private Shell state, suspend/resume, and concurrent sessions. |
| Broker -> Flatpak through Malcontent | Documented Malcontent/Flatpak application IDs are the only claimed Flatpak primitive. | Misleading desktop metadata, wrapper ambiguity, and launch routes not covered by that public integration. |
| Broker -> fapolicyd | Broker derives product-owned rules, atomically replaces them, verifies reload, and rolls back. | Missing daemon, reload timeout/failure, rule collision, unsupported file identity, and paths with special characters. |

The parent app, child extension, and kiosk are all untrusted front ends at the
broker boundary.  Code started by the child has the same authority as the
extension.  The kiosk account is not an approver.  Adapters are trusted to
translate supported APIs, but they do not decide policy or expand an
authorization.

## Required failure behavior

These are target requirements.  Rows owned by incomplete hardening tasks are
not current guarantees and cannot be advertised as such.

| Condition | Required behavior |
| --- | --- |
| Invalid request, unauthorized role, malformed value, or ineligible target | Reject before authorization and make no policy or grant write. |
| Direct child D-Bus/Polkit invocation | Apply the same caller, target, request, and selected-parent validation as the supported UI path. |
| Parent denial, wrong password, cancellation, timeout, disconnected authentication agent, or Polkit failure | Make no write and return a non-approved result. |
| Caller disconnects or caller, child, or approver changes identity, role, eligibility, or enabled state | Revalidate at the specified transaction boundaries; fail closed without a write, or restore the old state if a write already began. |
| Concurrent, repeated, or duplicate-completion request | Serialize the transaction for the target; never double-count a grant or replay relaxation. |
| Usage query is unavailable, busy beyond bounded retry, malformed, excessive, or made under the wrong parent identity | Do not grant time or relax an app filter. |
| Any write, read-back, execution-policy activation, or rollback step fails | Never report approval.  Restore the complete old state, or publish a distinct critical inconsistency if restoration cannot be verified. |
| fapolicyd is unavailable or cannot load verified rules | Keep unrelated broker reads available; mark app enforcement degraded/inconsistent; fail closed for app mutations and app-relaxing requests until reconciliation succeeds. |
| AccountsService, extension, or execution state drifts from canonical policy | Recompute from validated preferences and reconcile idempotently without importing drift or unintentionally clearing a valid grant. |
| Preference data is malformed, unsafe, belongs to a deleted identity, or is incompatible | Do not replace it with defaults or attach it to a reused UID; surface a redacted failure and require migration/reconciliation. |
| Timer, PAM, GNOME Shell, Flatpak, or login enforcement cannot meet an in-scope guarantee through supported APIs | Block release for that guarantee; do not substitute private or undocumented integration. |

## Supported claims, limitations, and release blockers

No application restriction may be called enforceable merely because its
launcher is hidden.  A desktop ID is not a process identity.  H-31 must assign
each catalog entry a stable supported identity or an explicit unsupported or
shared-runtime classification; H-32 implements that design and H-33 proves it
on a disposable VM.  Until those tasks pass, alternate-path resistance is not
a product guarantee.

The following are explicit product limitations until H-31 classifies them and
H-32/H-33 provide passing evidence: copied, renamed, replaced, or hard-linked
binaries; scripts and interpreters; shared wrappers; application updates;
Snap, Steam, and Waydroid applications; and any path whose fapolicyd identity
cannot be represented safely.  Such entries must be grouped honestly or not
offered as independently enforceable.  Flatpak protection is limited to the
documented Malcontent/Flatpak mechanism and must also pass the VM matrix.

GNOME Shell 50 exposes no supported extension API for adding a custom request
control to its stock parental-controls lock screen.  Requests are therefore
in-session only.  The product must not claim custom lock-screen request UI or
use private `TimeLimitsManager`, `AuthPrompt`, `ScreenShield`, or Polkit state.

The following are release blockers, not acceptable limitations:

- a denied, cancelled, disconnected, invalid, or partially failed request can
  grant time or relax policy;
- one authorization can be reused for a different operation or as a direct
  general AccountsService capability;
- a permanent block is relaxed by any failed or conditional request;
- an application advertised as enforceable has a demonstrated in-scope bypass;
- an exhausted managed child can obtain a usable session through a tested
  supported-platform timer or login race;
- CVE-2026-44931 remains exploitable on the selected supported package; or
- the required clean-VM matrix has not passed for the release.

Known current gaps are tracked rather than hidden: live VM coverage of the
broker-mediated child request remains part of H-51; fapolicyd availability is
still coupled to broker startup until H-22/H-30; backend drift reconciliation
and health reporting await H-20 through H-22; and no automated live VM harness
exists until H-50.  These are hardening work items, not completed guarantees.

## Requirements-to-test matrix

`Unit` means a host-safe automated unit or source-contract test.  `VM` means a
test inside the guarded disposable Ubuntu integration environment created by
H-50.  “Existing” describes current test evidence; a planned test is not proof
that its guarantee is implemented today.  H-51 assembles the end-to-end rows,
and H-52 prevents release without their passing artifacts.

| ID | In-scope bypass or requirement | Required evidence | Status / owner |
| --- | --- | --- | --- |
| TM-01 | Child or kiosk forges a target UID, caller role, or eligibility. | Unit caller/role/target cases; VM raw D-Bus calls from each account role. | Existing core coverage; extend in H-11/H-51. |
| TM-02 | Child selects a non-admin, remote, locked, changed, or fabricated approver. | Unit fresh-account and selected-approver checks; VM account mutation during prompt. | Existing partial coverage; H-10/H-11/H-51. |
| TM-03 | Child invokes the product Polkit action directly or spoofs action details. | Unit policy/detail/subject tests; VM direct `CheckAuthorization` and raw broker-call tests. | H-11/H-13/H-51. |
| TM-04 | Retained or replayed authorization permits direct `AppFilter` or `ActiveExtension` writes. | Source contract proving no child write/imply path; VM write attempt before and after one request. | H-11/H-12/H-51. |
| TM-05 | Denial, cancellation, wrong password, timeout, agent loss, or disconnect still changes state. | Unit no-write failure injection; VM authentication lifecycle matrix. | Existing denial/disconnect/agent-loss coverage; H-10/H-11/H-13/H-51. |
| TM-06 | Caller, child, or approver identity/role changes between validation, authorization, usage query, and write. | Unit mutation at every boundary; VM promotion, deletion, lock, UID-reuse, and bus-disconnect cases. | Existing partial coverage; H-10/H-13/H-21/H-51. |
| TM-07 | Concurrent, repeated, or duplicate-completion requests produce double grants or stale relaxation. | Unit state-machine concurrency/replay tests; VM simultaneous child/kiosk requests. | Existing single-flight coverage; H-10/H-13/H-51. |
| TM-08 | Forged, malformed, excessive, busy, or wrong-identity usage data changes a grant. | Unit helper bounds/validation and grant arithmetic; VM daemon busy/failure/identity cases. | Existing partial coverage; H-10/H-13/H-41/H-51. |
| TM-09 | Grant accumulation, expiry, or rest-of-day arithmetic creates unintended access. | Unit boundary, overflow, DST, and formula tests; VM accumulated, expiry, midnight, and rest-of-day flows. | Existing formula/DST coverage; H-10/H-13/H-41/H-51. |
| TM-10 | Failure before/after a write or read-back reports approval or leaves partial time/app state. | Unit failure at every transaction transition and rollback; VM service interruption at each writable stage. | Existing partial rollback coverage; H-10/H-13/H-51. |
| TM-11 | A failed conditional request relaxes a permanent block. | Unit old/desired-state invariants at every failure point; VM denial and injected-backend cases. | H-10/H-13/H-51. |
| TM-12 | External AccountsService state becomes canonical or backend drift persists. | Unit idempotence, drift, deletion, and signal-storm tests; VM external mutation/restart tests. | H-20/H-21/H-51. |
| TM-13 | fapolicyd outage blocks the broker or lets an app mutation/relaxation succeed. | Unit daemon-down, timeout, rollback, recovery, and unrelated-read cases; VM daemon-stop/recovery cases. | Existing atomic-rule rollback coverage; H-22/H-30/H-51. |
| TM-14 | Launcher hiding is mistaken for native execution denial. | VM direct executable and direct desktop-file launches, with visible state and derived rules asserted separately. | H-31/H-32/H-33/H-51. |
| TM-15 | Copy, hard link, rename, identical copy, executable replacement, whitespace/comma path, script, or interpreter bypasses an advertised native block. | Identity fixtures plus positive and negative VM execution tests under managed/admin/unrelated UIDs. | H-31/H-32/H-33/H-51; unsupported cases stay limitations. |
| TM-16 | Shared wrappers or Snap, Steam, or Waydroid launchers are presented with false per-app isolation. | ADR classification, collision-state unit tests, and VM group/unsupported behavior. | H-31/H-32/H-33/H-51. |
| TM-17 | Flatpak alternate launch bypasses an advertised Flatpak block. | Unit application-ID projection plus VM desktop, CLI, approved-relaxation, expiry, and unrelated-user tests. | H-31/H-32/H-33/H-51. |
| TM-18 | Missing/uninstalled targets, app updates, or identity collisions silently discard or misapply saved policy. | Unit catalog/migration/reconciliation fixtures; VM uninstall/reinstall/update flows. | Existing missing-target coverage; H-21/H-31/H-32/H-33/H-51. |
| TM-19 | Exhausted child logs in through timer/PAM startup, crash, corrupt store, or read-only-store behavior. | Disposable-VM fresh-login matrix with service and store faults. | H-40/H-41/H-51. |
| TM-20 | Clock adjustment, DST, midnight, suspend/resume, idle time, or concurrent sessions yields extra time. | Unit time-boundary logic where pure; VM observed timer/session matrix. | Existing local-midnight unit coverage; H-41/H-51. |
| TM-21 | Ordinary local user causes unbounded Malcontent timer storage growth. | Disposable-VM abuse bound and legitimate high-volume regression tests. | H-40/H-51; release-blocking until fixed. |
| TM-22 | Child reads/writes preferences, unsafe records are accepted, or policy follows a reused UID. | Unit ownership/schema/migration/UID-lifecycle tests; VM filesystem permission and account-reuse tests. | Existing preference/migration coverage; H-21/H-51. |
| TM-23 | Front end writes another component's logs, injects sensitive fields, or grows logs without bound. | Unit role/redaction/retention tests; VM permission and raw D-Bus logging attempts. | Existing log/core coverage; H-51/H-60. |
| TM-24 | Private GNOME APIs create an unsupported lock-screen or session guarantee. | Source-contract rejection plus supported-image VM behavior. | Existing source contract; H-41/H-51. |
| TM-25 | Install, upgrade, activation, migration, or uninstall leaves unsafe/stale policy. | Unit installer/migration/activation/uninstall tests; clean-install and upgrade VM jobs. | Existing unit coverage; H-50/H-51/H-52. |

Every in-scope bypass above has both an owning implementation/design task and a
required test destination.  No row requiring VM evidence is complete until its
artifact is captured on the supported image and accepted by H-52.
