# Snap app-limit limitations and options

Status and developer scope decision: 2026-11-05. This document owns the known
Snap enforcement limitation, investigation findings and possible future work.
Product enforcement is unchanged. Snap remediation is separate from the active
[E2E plans](TestAutomation/E2E-Execution-Instructions.md#snap-acceptance-boundary).

## Today's behavior

Parent can discover Snap launchers, save Allowed/Hard/Soft choices and read those
choices back. Allowed command launch, normal input, captured activity and a
separate second window were qualified with the repository's Snap fixtures on
Fedora 44. Saving a block is not proof that execution is blocked or an existing
app has closed. Launcher filtering can work while execution remains possible.

| Boundary | Established result | Limit of the evidence |
| --- | --- | --- |
| Fedora running-app closure | The captured Hard fixture stayed alive after Parent saved Hard and returned to the original child session. The installed terminator found no matching Snap label. | SELinux was enforcing, the payload was `unconfined_t`, and the kernel lacked AppArmor. Declared strict installation did not provide the required AppArmor identity. |
| Fedora fresh launch | With Hard still saved, the actual fixture payload ran through `snap run` and the public Snap command after the original process was closed. A new payload also remained alive through the normal desktop command mechanism. | Engineering probes establish process admission; they do not qualify a usable new window or every Snap package. |
| Ubuntu strict Snaps | Strict Snap confinement normally provides per-app AppArmor identities, a stronger basis for running-process discovery. | Our installed closure and blocked-launch results were not qualified on Ubuntu. The shared command-path rule design still has a gap. |
| Soft blocks and approvals | Saved conditional choices and approval state are separate from actual Snap enforcement. | Task 109 stopped in the Hard branch. Soft denial, restoration and approval-driven closure have no passing acceptance from that attempt. Do not infer either success or a live-tested failure matrix. |
| Classic Snaps | VS Code's official Snap uses `--classic`. | Strict-Snap isolation and identity assumptions cannot automatically be transferred to classic payloads; inspect their actual identity before making a guarantee. |

The source preserves `/snap/bin/<command>` or
`/var/lib/snapd/snap/bin/<command>` as the app-filter identity. These commands
are symlinks to the shared Snap launcher, not necessarily the app payload.
Malcontent compares launcher command paths; the generated execution rules also
use that public path, while fapolicyd resolves event symlinks to their targets.
An alternate route is therefore not covered merely by saving that launcher
path. Copying the symlink/shared launcher is not necessarily a working copy of
the app; copying is not needed for the demonstrated bypass.

See [catalogue identity](../broker/oh_no_parent_control/catalog.py),
[execution rules](../broker/oh_no_parent_control/execution_policy.py),
[process termination](../broker/oh_no_parent_control/app_termination.py) and the
[task 109 investigation](TestAutomation/E2E-Tasks/109-snap.md#current-handoff).
Its retained failed acceptance is
`snap-policy-closure.hard-prior-window-closure`; the formal furthest checkpoint
is `snap-policy-closure.hard-policy-saved-and-child-returned`. Later maintenance
experiments are diagnosis, not acceptance. No product correction was applied.

## Why a user-owned group is insufficient

Live experiments used the child's real user-manager D-Bus connection:

- The child placed an unrelated owned process into a correctly named
  `snap.<package>.<app>-<UUID>.scope`.
- The child moved the captured running Snap payload into another scope. Its
  PID/start time and executable remained unchanged and it stayed alive.

Matching the exact UID, full tag and UUID does not repair either weakness.
Scope matching can select unrelated work or miss the real app after migration.
A read-only Snap mount identifies a package, not necessarily one app within a
multi-app package. Neither fact replaces the kernel-applied per-app identity
required by the current [security contract](Threat-Model.md#assets-and-authorities).
These were systemd cgroup scopes, not Unix process groups.

## Remaining execution-control obstacles

The package-monitoring experiments did not establish selective enforcement:

- Normal monitoring did not stop the blocked payload. Package-directory rules
  alone were insufficient; squashfs monitoring was not enabled by default.
- Enabling filesystem marks failed in enforced `fapolicyd_t`. An
  enforced/permissive/enforced comparison isolated a domain restriction, but
  the exact missing permission and supported repair remain unproved.
- With temporary diagnostic monitoring working, the blocked package's metadata
  access could be intercepted. However, both the blocked and Allowed Snap then
  failed at the shared `snap-exec` helper under stock untrusted-execute policy.
  Device attribution at that event was unavailable. This was not selective
  package enforcement or a successful fix.

Temporary rules, domain exceptions and configuration changes were restored;
owned workers stopped and baseline restoration finished. No saved VM state,
maintenance ownership or temporary exception is a prerequisite for future work.
The next hash-attribution probe recorded in task 109 belongs only to an
explicitly requested Snap-remediation investigation.

## Established approaches and what we could adopt

The following describes upstream documentation reviewed on 2026-11-05, not
qualification of those products on our VMs.

| Approach or product | How it works | Possible adoption and remaining limits |
| --- | --- | --- |
| [Malcontent](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/main/README.md) | Stores app filters; participating desktops, stores and launchers query and apply them. Flatpak can refuse a launch through its integrated check. Upstream explicitly does not claim mandatory access control. | Retain our existing integration for discovery/filtering and supported launch checks. It does not supply a universal Snap admission gate or running-app termination identity. |
| [Timekpr-nExT PlayTime](https://git.launchpad.net/timekpr-next/tree/README.md?h=master) | Monitors per-user processes against administrator-defined executable patterns and, optionally, command lines. At restriction it terminates matches and kills persistent matches; relaunches are detected and terminated again. See its [implementation](https://git.launchpad.net/timekpr-next/tree/server/user/playtime.py?h=master). | A practical fallback could combine validated child UID and verified package-specific executable paths, with names/arguments as supporting evidence. Cgroup migration alone would not defeat this matching. It remains detect-and-kill: execution precedes detection; narrow patterns miss helpers, broad patterns kill allowed work, and names/arguments are weaker identity. |
| [fapolicyd](https://github.com/linux-application-whitelisting/fapolicyd/blob/v2.0.1/doc/fapolicyd.rules.5) | Mediates monitored file access/execution using rules including UID, path, device and file hash. | Extend our existing backend to the actual payload rather than its public symlink. Hashes can cover unchanged copies at other paths, provided events are intercepted; updates change hashes and shared interpreters/helpers complicate app isolation. Snap monitoring and Allowed-app preservation remain unresolved. Admission still needs separate existing-process closure. |
| [Snap AppArmor confinement](https://snapcraft.io/docs/explanation/security/security-policies/) | Kernel-applied profiles identify/constrain strict Snap apps on a supporting system. | Prefer this identity where actually available. The profile is not our Hard/Soft policy; policy integration and live qualification are still required. Fedora findings and classic apps prevent a universal assumption. |
| Root-controlled launch and containment | A privileged owner admits launches into a boundary the child cannot modify or escape through the user manager. | A possible redesign, not an implemented fix. It must cover alternate launches, descendants, user-bus requests and shared runtimes. Merely setting a cgroup name or making its filesystem read-only does not prevent a privileged manager from moving processes on the child's behalf. |
| [ThreatLocker Linux application control](https://threatlocker.kb.help/threatlocker-as-an-essential-eight-maturity-model-mitigation-strategy/) | Documents kernel-level application control and [built-in Snap application definitions](https://threatlocker.kb.help/linux-built-ins-2025/). | A credible commercial evaluation candidate and example of curated application identities. Definitions do not prove per-child Hard/Soft semantics, immediate closure, exact distro support or bypass resistance. No integration or purchase is selected. |
| [DriveLock Linux application control](https://www.drivelock.help/versions/2025_2/web/en/complete/content/linuxagent/concepts/con_lin_systemreqac.htm) | Documents fanotify-based execution control and squashfs support; its Linux rules include [hash-based allowlisting](https://www.drivelock.help/versions/2024_1/pdf/en/DriveLock_ProductDocumentation_2024-1_EN.pdf). | Another admission-control example, not proof of our Snap semantics. It explicitly excludes coexistence with other fanotify-based security products; it is not an add-on to install beside our existing backend. |
| [Airlock Digital](https://www.airlockdigital.com/practical-allowlisting-and-execution-control) | Enterprise Linux execution control; its published support page says Snap packages execute unrestricted. | Not an established solution to this requirement without newer vendor confirmation and qualification. |

Microsoft documents [VS Code's classic installation](https://code.visualstudio.com/docs/setup/linux).
Snap documents [classic versus strict confinement](https://snapcraft.io/docs/explanation/security/classic-confinement/).
Classic confinement is another reason to avoid treating all Ubuntu Snaps as
strict-label fixtures.

## Product choices reserved for separate work

Possible choices are to expose unsupported Snap enforcement honestly; implement
a documented best-effort monitor; investigate whole-package controls; or invest
in a stronger admission/containment integration. Whole-package controls change
multi-app semantics. Global Snap disablement also affects parents and other
children, so it does not satisfy our per-child requirement.

For a best-effort monitor, Hard matches would always be terminated; Soft matches
would be terminated only while the effective policy blocks them. Approval and
restoration must follow authoritative current policy, including the existing
[natural-expiry behavior](SystemDesign/Applications.md#session-entry-reconciliation).
Choosing a monitor does not itself fix policy-transition timing or launch
admission. No name-matching fallback, broader package policy, permanent security
exception, upstream change or new product warning is implemented by this document.

## E2E scope decision

The developer explicitly separated Snap remediation from E2E on 2026-11-05.
Active work accepts today's supported behavior without claiming blocked Snap
execution is reliable. Both plans use the
[shared Snap acceptance boundary](TestAutomation/E2E-Execution-Instructions.md#snap-acceptance-boundary).

Task 109 and enforcement tasks 114/114b/115/115b/111/112/281/284 remain unchecked
under Plan B's deferred work. Cases 88/90/94/95/96/97/239/242 retain their IDs,
pending status and no executable. They have no current-release consumer and
cannot hold either active plan's pointer. Their old denial/closure recipes are
future remediation targets, not today's supported behavior or expected failures
that should be made to pass. Do not resume them or request another product
choice during ordinary E2E work.

Allowed Snap grid qualification 109a and case 86/task 110 remain active, depending
on completed allowed-command task 109b rather than deferred enforcement. Existing
completed fixture/use tasks 109p/109b/113/113b stay complete. Other E2E cases use
their declared native, Flatpak or game identities; no general app-block assertion
implicitly adds a Snap matrix. New unrelated failures retain normal handling.

Return condition for deferred work: an explicit developer request to resume Snap
remediation, followed by a chosen supported contract and causal qualification
before the cases are returned to an active queue. Resolving that choice is not
an active E2E prerequisite. This scope decision grants no passing acceptance and
does not weaken native/Flatpak assertions or the existing process-ownership guards.
