# Threat model and enforcement guarantees

## Scope and attacker

Oh No! Parent Control manages time and application policy for a local, non-administrator child account. The product's target security architecture assigns policy decisions, authorization scoping, transactions, reconciliation, and health reporting to the privileged system D-Bus broker. Supported operating-system services supply enforcement mechanisms behind that boundary. Launcher visibility is not enforcement, and Malcontent alone is not a hard security boundary.

The in-scope attacker is a managed child who can:

- use a terminal and run arbitrary code as their own UID;
- create, edit, and directly open desktop launchers;
- copy, rename, replace, hard-link, and execute files wherever their account has permission;
- construct arbitrary public system D-Bus calls, including calls which bypass all product front ends; and
- invoke product and backend Polkit actions and control the lifetime of their own processes and D-Bus connections.

Copying a binary, constructing a D-Bus call, and invoking a Polkit action are therefore explicitly in scope. None of those acts is proof of authorization. A successful parent authentication may authorize only the child, duration, end-of-day mode, and conditional-app choice displayed for that request. It must not confer a reusable or general AccountsService capability.

The attacker does **not** possess administrator credentials, cannot become root, cannot modify the boot chain, and cannot exploit kernel vulnerabilities. Compromised or voluntarily disclosed administrator credentials, existing root access, offline disk modification, alternate boot media, boot-chain compromise, firmware compromise, and kernel exploits are out of scope. A flaw in an integrated service that an ordinary user can exercise through an in-scope operation is not excluded; the timer/storage coverage obligation remains in the matrix below. Parent credentials remain an asset: the product must not collect, persist, log, or expose credentials entered into the trusted Polkit agent.

Remote administration, web filtering, GUI appearance, physical denial of service, and replacement of Malcontent as a whole are outside this security review's scope.

## Assets and authorities

The [state design](SystemDesign/State.md) defines current ownership. The protection column includes security expectations that still require the executable evidence identified below; this table is not a completion claim.

| Asset | Authority | Required protection |
| --- | --- | --- |
| Daily allowance and enablement | Validated product preferences; projected to AccountsService | A child cannot change the configured limit or enablement state. |
| Runtime grants | AccountsService `ActiveExtension` | Only a complete, verified, parent-approved transaction can create or extend a grant. |
| Permanent app blocks | Validated product preferences | No access request, backend failure, or conditional relaxation may remove them. |
| Conditional app blocks | Validated product preferences | They relax only when that choice was displayed, authorized, and successfully committed with the grant. |
| Parent credentials | Parent and trusted Polkit authentication agent | Product processes never receive, store, log, or delegate the secret to a child. |
| Preference records | Root-owned `/var/lib/oh-no-parent-control/preferences/<uid>.json` | Front ends cannot access records directly; the broker schema-validates and atomically writes them. |
| Timer usage | `malcontent-timerd` | Only validated usage obtained through the documented identity-scoped public query contributes to grant calculation. |
| Generated execution rules | Broker-derived fapolicyd rule file | Rules are a verified, atomic projection of canonical app policy and apply only to the intended UID. |
| Running blocked applications | Broker-derived app identities and kernel process ownership | An app-policy save, approved no-soft-app request, or parent revocation terminates matching processes only for its validated selected child UID; Snap processes additionally require the kernel-applied application security label, and identical applications owned by other UIDs are untouched. |
| Audit logs | Root broker daily log writer | Logs are access-controlled, bounded, redacted, attributable to the correct component, and never writable directly by a child. |

Preferences are canonical only for configured product policy. AccountsService policy and fapolicyd rules are derived enforcement state, `malcontent-timerd` is authoritative for measured usage, and AccountsService `ActiveExtension` is authoritative for a live grant. External or derived state must never be imported silently into preferences.

## Trust boundaries

| Boundary | Trusted responsibility | Input or failure treated as untrusted |
| --- | --- | --- |
| Front ends -> system D-Bus | D-Bus supplies a unique live sender name; front ends only present choices and results. | Every method argument, UI-side calculation, label, claimed UID, and caller-controlled disconnection. |
| System D-Bus -> broker service | The broker resolves sender credentials, assigns caller role, validates targets, and returns redacted stable errors. | Calls which omit the UI, are reordered, repeated, malformed, or sent by arbitrary child code. |
| Broker service -> broker policy core | The service performs binding and error translation only; the core owns product policy and transaction order. | Adapter exceptions, stale objects, malformed backend values, and re-entrant/concurrent work. |
| Broker -> preference store | Broker validates the complete schema and uses secure atomic replacement. | Malformed records, symlinks, unsafe ownership or mode, future schemas, UID reuse, and interrupted writes. |
| Broker -> Polkit/authentication agent | The broker constructs the action details and Polkit authenticates the selected parent for that exact action. | Caller-selected identity, spoofed details, denial, cancellation, timeout, agent loss, retained authorization, and subject changes. |
| Broker -> AccountsService/Malcontent account API | Broker computes desired account state, orders writes, verifies read-back, and rolls back failure. | Service outage, partial writes, stale users, external changes, and malformed properties. |
| Broker -> Malcontent timer daemon and usage helper | `malcontent-timerd` measures usage; the identity-scoped helper performs the documented child self-read or authenticated parent query. | Busy/unavailable service, excessive or malformed output, wrong parent identity, corrupt storage, and clock/session anomalies. |
| PAM/GDM/GNOME Shell -> Malcontent | Only documented public login, session-limit, signal, and query integration is supported. | Startup races, crash/restart, missing services, private Shell state, suspend/resume, and concurrent sessions. |
| Broker -> Flatpak through Malcontent | Documented Malcontent/Flatpak application IDs are the only claimed Flatpak primitive. | Misleading desktop metadata, wrapper ambiguity, and launch routes not covered by that public integration. |
| Broker -> fapolicyd | Broker derives product-owned rules, atomically replaces them, verifies reload, and rolls back. | Missing daemon, reload timeout/failure, rule collision, unsupported file identity, and paths with special characters. |

The parent app, child extension, and kiosk are all untrusted front ends at the broker boundary. Code started by the child has the same authority as the extension. The kiosk account is not an approver. Adapters are trusted to translate supported APIs, but they do not decide policy or expand an authorization.

## Required failure behavior

These are security review targets. Current behavior and readiness boundaries are defined in [System-Design.md](System-Design.md); unverified targets or conflicts must be resolved explicitly in the automation audit before they are advertised as guarantees.

| Condition | Required behavior |
| --- | --- |
| Invalid request, unauthorized role, malformed value, or ineligible target | Reject before authorization and make no policy or grant write. |
| Direct child D-Bus/Polkit invocation | Apply the same caller, target, request, and selected-parent validation as the supported UI path. |
| Parent denial, wrong password, cancellation, timeout, disconnected authentication agent, or Polkit failure | Make no write and return a non-approved result. |
| Caller disconnects or caller, child, or approver changes identity, role, eligibility, or enabled state | Revalidate at the specified transaction boundaries; fail closed without a write, or restore the old state if a write already began. |
| Concurrent, repeated, or duplicate-completion request | Serialize the transaction for the target; never double-count a grant or replay relaxation. |
| Usage query is unavailable, busy beyond bounded retry, malformed, excessive, or made under the wrong parent identity | Do not grant time or relax an app filter. |
| Any write, read-back, execution-policy activation, or rollback step fails | Never report approval. Restore the complete old state, or publish a distinct critical inconsistency if restoration cannot be verified. |
| Blocked-app discovery, ownership verification, signalling, or exit verification fails | Do not activate a new grant or report a revocation as successful. If termination may have begun, keep the selected child's complete canonical block filter while restoring reversible time state; never signal an unverified or different UID. |
| fapolicyd is unavailable or cannot load verified rules | Follow the documented fail-closed startup/readiness contract and reject mutations or relaxation without verified enforcement; distinguish startup failure from an error after the broker was ready. |
| AccountsService, extension, or execution state drifts from canonical policy | Recompute from validated preferences and reconcile idempotently without importing drift or unintentionally clearing a valid grant. |
| Preference data is malformed, unsafe, belongs to a deleted identity, or is incompatible | Do not replace it with defaults or attach it to a reused UID; surface a redacted failure and require migration/reconciliation. |
| Timer, PAM, GNOME Shell, Flatpak, or login enforcement cannot meet an in-scope guarantee through supported APIs | Block release for that guarantee; do not substitute private or undocumented integration. |

## Supported claims, limitations, and release blockers

No application restriction may be called enforceable merely because its launcher is hidden. A desktop ID is not a process identity. Test the supported native, Snap and Flatpak identities and launch routes defined by [Specification.md](Specification.md) and [application policy](SystemDesign/Applications.md). Installed and graphical evidence must prove actual allow/deny behavior and other-user isolation.

Independently copied/renamed executables, shared interpreters and ambiguous wrappers must be tested against the documented support limits; do not invent per-payload guarantees. App updates, supported Snap identities and Flatpak routes remain required coverage and cannot be discarded as optional because a test is unfinished. For Steam, Waydroid or other shared launchers, review exactly the identity and behavior advertised by the product rather than assuming blanket per-app isolation.

The product offers the child-session request overlay and the dedicated kiosk entered through GDM. It has no custom request control inside the stock lock screen. Test those real entry paths; do not create a private Shell or Polkit integration to make a scenario pass.

The following are release blockers, not acceptable limitations:

- a denied, cancelled, disconnected, invalid, or partially failed request can grant time or relax policy;
- one authorization can be reused for a different operation or as a direct general AccountsService capability;
- a permanent block is relaxed by any failed or conditional request;
- an application advertised as enforceable has a demonstrated in-scope bypass;
- an exhausted managed child can obtain a usable session through a tested supported-platform timer or login race; or
- the required clean-VM matrix has not passed for the release.

CVE-2026-44931 is retained as a reference for supported-package security review,
not as a standalone release blocker.

The guarded installed-system runner and local regression suites exist. Installed
authorization work remains in Task 14, and graphical customer coverage and the
comprehensive gate remain unfinished. Use the [automation backlog](TestAutomation/Test-Automation.md)
and current-run evidence for status; historical hardening task numbers or an
old pass count do not establish a present guarantee. The [system design](System-Design.md)
and [specification](Specification.md) define current supported behavior; resolve
conflicts with earlier target proposals before claiming their acceptance.

## Requirements-to-test matrix

`Unit` means local unit/property or supporting source-contract evidence. `System`
means real installed OS/caller tests in the guarded existing VM; `E2E` means a
continuous real graphical customer journey. Source contracts and local doubles
cannot fulfill installed or E2E requirements. The owners below refer to the
[remaining automation tasks](TestAutomation/Test-Automation.md#unfinished-tasks);
they are coverage destinations, not completion claims. Task 28B audits the
scope and current-run evidence, including unresolved security requirements.

| ID | In-scope bypass or requirement | Required evidence | Automation owner / scope |
| --- | --- | --- | --- |
| TM-01 | Child or kiosk forges a target UID, caller role, or eligibility. | Unit caller/role/target cases; VM raw D-Bus calls from each account role. | Task 14; graphical targeting in Tasks 21/23/24. |
| TM-02 | Child selects a non-admin, remote, locked, changed, or fabricated approver. | Unit fresh-account and selected-approver checks; VM account mutation during prompt. | Tasks 14, 23A and 24B; stale selection in 26A. |
| TM-03 | Child invokes the product Polkit action directly or spoofs action details. | Unit policy/detail/subject tests; VM direct `CheckAuthorization` and raw broker-call tests. | Task 14; actual prompt and post-approval checks in 23A/24B. |
| TM-04 | Retained or replayed authorization permits direct `AppFilter` or `ActiveExtension` writes. | Source contract proving no child write/imply path; VM write attempt before and after one request. | Task 14 and Tasks 23A/24B. |
| TM-05 | Denial, cancellation, wrong password, timeout, agent loss, or disconnect still changes state. | Unit no-write failure injection; VM authentication lifecycle matrix. | Tasks 14, 23/24 and 26A. |
| TM-06 | Caller, child, or approver identity/role changes between validation, authorization, usage query, and write. | Unit mutation at every boundary; VM promotion, deletion, lock, UID-reuse, and bus-disconnect cases. | Task 14; account lifecycle/approval races in 26A. |
| TM-07 | Concurrent, repeated, or duplicate-completion requests produce double grants or stale relaxation. | Unit state-machine concurrency/replay tests; VM simultaneous child/kiosk requests. | Task 17A and Tasks 23A/24B/26A. |
| TM-08 | Forged, malformed, excessive, busy, or wrong-identity usage data changes a grant. | Unit helper bounds/validation and grant arithmetic; VM daemon busy/failure/identity cases. | Tasks 14, 16A and 26A. |
| TM-09 | Grant accumulation, expiry, or rest-of-day arithmetic creates unintended access. | Unit boundary, overflow, DST, and formula tests; VM accumulated, expiry, midnight, and rest-of-day flows. | Tasks 16A/17 and 22/23/24/26C. |
| TM-10 | Failure before/after a write or read-back reports approval or leaves partial time/app state. | Unit failure at every transaction transition and rollback; VM service interruption at each writable stage. | Tasks 15B/17A and 21B/26A. |
| TM-11 | A failed conditional request relaxes a permanent block. | Unit old/desired-state invariants at every failure point; VM denial and injected-backend cases. | Tasks 15B/17 and 23A/25B/26A. |
| TM-12 | External AccountsService state becomes canonical or backend drift persists. | Unit idempotence, drift, deletion, and signal-storm tests; VM external mutation/restart tests. | Tasks 17/18 and 26A/26B; reconcile expectations with current system design. |
| TM-13 | fapolicyd outage permits unverified enforcement or a successful app mutation/relaxation. | Unit startup/runtime failure, timeout, rollback and recovery cases; real VM daemon-stop/recovery and readiness checks. | Tasks 15B/20/26A; distinguish fail-closed startup from live failure. |
| TM-14 | Launcher hiding is mistaken for native execution denial. | VM direct executable and direct desktop-file launches, with visible state and derived rules asserted separately. | Tasks 15A and 25A. |
| TM-15 | Copy, hard link, rename, identical copy, executable replacement, whitespace/comma path, script, or interpreter bypasses an advertised native block. | Identity fixtures plus positive and negative VM execution tests under managed/admin/unrelated UIDs. | Tasks 15A/25A; assert documented support limits rather than inventing broader enforcement. |
| TM-16 | Shared wrappers or Snap, Steam, or Waydroid launchers are presented with false per-app isolation. | ADR classification, collision-state unit tests, and VM group/unsupported behavior. | Tasks 15/25 and final scope review in 28B. |
| TM-17 | Flatpak alternate launch bypasses an advertised Flatpak block. | Unit application-ID projection plus VM desktop, CLI, approved-relaxation, expiry, and unrelated-user tests. | Tasks 15A/25A/25B. |
| TM-18 | Missing/uninstalled targets, app updates, or identity collisions silently discard or misapply saved policy. | Unit catalog/migration/reconciliation fixtures; VM uninstall/reinstall/update flows. | Tasks 15A/18/25A/26B. |
| TM-19 | Exhausted child logs in through timer/PAM startup, crash, corrupt store, or read-only-store behavior. | Guarded-VM fresh-login matrix with service and store faults. | Task 16B and Tasks 20/22A/26A. |
| TM-20 | Clock adjustment, DST, midnight, suspend/resume, idle time, or concurrent sessions yields extra time. | Unit time-boundary logic where pure; VM observed timer/session matrix. | Tasks 16 and 22/26B; controlled clocks are separately labeled. |
| TM-21 | Ordinary local user causes unbounded Malcontent timer storage growth. | Guarded-VM abuse bound and legitimate high-volume regression tests. | Task 16B security-boundary review; unresolved exposure blocks applicable acceptance. |
| TM-22 | Child reads/writes preferences, unsafe records are accepted, or policy follows a reused UID. | Unit ownership/schema/migration/UID-lifecycle tests; VM filesystem permission and account-reuse tests. | Tasks 14/18B/26A. |
| TM-23 | Front end writes another component's logs, injects sensitive fields, or grows logs without bound. | Unit role/redaction/retention tests; VM permission and raw D-Bus logging attempts. | Task 14 and Task 27; log-source permissions and export redaction are distinct. |
| TM-24 | Private GNOME APIs create an unsupported lock-screen or session guarantee. | Source-contract rejection plus supported-image VM behavior. | Local source guards and Tasks 19/22/24. |
| TM-25 | Install, upgrade, activation, migration, or uninstall leaves unsafe/stale policy. | Unit installer/migration/activation/uninstall tests; clean-install and upgrade VM jobs. | Tasks 18/20/26C; final gate in 28. |

Each applicable threat must map to executable tests and accepted evidence in
the declared supported environment. A documentation owner or an existing file
is insufficient. Unresolved support/requirement conflicts and missing real
runtime evidence must be visible in the final audit; they cannot disappear
through mock results, a baseline restore, or a renamed task.
