# System design

Oh No! Parent Control has three unprivileged front ends around one privileged
system D-Bus broker. The broker owns runtime product policy and cross-account
writes. Operating-system services provide enforcement behind that boundary.

The installed product targets Ubuntu GNOME Desktop. Package installation accepts
Ubuntu 26.04 or newer; the functional acceptance baseline is Ubuntu 26.04 with
GNOME Shell 50, the version declared by the packaged child extension. The
installer's OS lower bound does not qualify every later GNOME version.
The [functional specification](Specification.md) describes customer actions and
results. This design describes the current implementation and its limits;
explicitly deferred designs and security targets are not implemented guarantees.

## How to read this design

This overview answers questions about component responsibilities, trust, and
state ownership. For a scoped question, read the relevant section of one module
below. Each module lists implementation files and conditional links to related
design; follow those links when the task crosses the named boundary. Stop when
you have the context needed for the task.

For example, a request-form layout change needs Front ends. Grant arithmetic
needs the Screen time calculation section; also read Broker transactions if
changing approval or commit behavior. A preference schema change needs
[State](SystemDesign/State.md) and [Data migration](SystemDesign/Data-Migration.md).

## Find the relevant design

| Area | Owning module | Direct sections for scoped questions |
| --- | --- | --- |
| Identity, D-Bus, authorization | [Broker](SystemDesign/Broker.md) | [Accounts](SystemDesign/Broker.md#accounts-and-roles), [method permissions](SystemDesign/Broker.md#broker-interface-and-roles), [approval/revocation](SystemDesign/Broker.md#authorization-and-grant-transactions) |
| Preferences and configuration | [State](SystemDesign/State.md) | [Schemas, defaults, and authorities](SystemDesign/State.md#persistent-and-derived-state) |
| Saved-data compatibility and upgrades | [Data migration](SystemDesign/Data-Migration.md) | [Package ordering and retries](SystemDesign/Data-Migration.md#package-lifecycle), [adding migrations](SystemDesign/Data-Migration.md#adding-a-preference-migration), [safety](SystemDesign/Data-Migration.md#safety-contract) |
| Time limits and child sessions | [Screen time](SystemDesign/Screen-Time.md) | [Enablement](SystemDesign/Screen-Time.md#screen-time-model), [calculations and usage](SystemDesign/Screen-Time.md#grant-arithmetic-and-usage-identities), [countdown/lock/PAM](SystemDesign/Screen-Time.md#countdown-and-expiry-enforcement) |
| Application enforcement | [Application policy](SystemDesign/Applications.md) | [Catalog](SystemDesign/Applications.md#application-policy-and-enforcement), [process matching](SystemDesign/Applications.md#running-application-identity), [execution rules](SystemDesign/Applications.md#live-filter-and-execution-rules), [session reconciliation](SystemDesign/Applications.md#session-entry-reconciliation) |
| Parent, child overlay, kiosk UI | [Front ends](SystemDesign/Frontends.md) | [Shared form and flows](SystemDesign/Frontends.md#main-flows), [remembered selectors](SystemDesign/Frontends.md#request-selector-state) |
| Startup, installation, upgrades | [Lifecycle](SystemDesign/Lifecycle.md) | [Readiness and activation](SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle), [installed layout](SystemDesign/Lifecycle.md#installed-layout) |
| Uninstall and purge | [Package removal](SystemDesign/Package-Removal.md) | [Rollback](SystemDesign/Package-Removal.md#payload-and-reversible-enforcement-cleanup), [account ownership](SystemDesign/Package-Removal.md#pam-and-kiosk-ownership), [purge/retry](SystemDesign/Package-Removal.md#remove-purge-and-retry) |
| Diagnostics and feedback | [Logging and feedback](SystemDesign/Logging-and-Feedback.md) | [Logs](SystemDesign/Logging-and-Feedback.md#logging), [editor/attachments](SystemDesign/Logging-and-Feedback.md#feedback-and-diagnostic-export), [HTTP retries](SystemDesign/Logging-and-Feedback.md#multipart-and-retry-contract) |

## Components and trust

| Component | Responsibility |
| --- | --- |
| Parent GTK app (`parent/`) | Child discovery; Screen Limits and App Limits; automatic saves, matching/filtering, time status and grant revocation; Help, About and feedback |
| Child GNOME Shell extension (`child/`) | Countdown, expiry lock, session-preparation requests, request-overlay and error-report launch, and a per-user countdown-animation context-menu preference; no separate settings window |
| Shared GTK request form (`kiosk/`) | Fullscreen child overlay and dedicated request-only kiosk session; account selection, time estimate, approval, remembered choices, results and error reports |
| Shared UI (`common/oh_no_parent_control_ui/`) | About, legal/help links, accessible control descriptions, duration formatting, rich feedback editor, attachments, diagnostic validation and HTTPS submission |
| Root broker (`broker/`) | Caller validation, account/catalog discovery, preference storage, time calculations, approval/revocation, app termination, OS adapters and bounded diagnostics |
| OS integrations | AccountsService live filters/limits/grants, Malcontent usage and PAM checks, fapolicyd native execution rules, GNOME locking/extension activation, Polkit authentication and the restricted kiosk session |

Front ends call the broker over system D-Bus. It derives caller identity from
bus credentials and revalidates roles, targets, and request inputs before
privileged writes. Front ends access private preferences only through the
broker. Parent startup tests the shared `ListManagedUsers` permission, which
allows administrators and the configured kiosk UID; policy management methods
apply their separate administrator check. The restricted kiosk session provides
no Parent launch route. The Parent App reads remaining time through
`GetTimeStatus`; it does not directly read another account's AccountsService
grant. The broker reads that grant and runs a fixed usage helper as the selected child for status, or
as the authenticated approver during a fixed-duration approval. The child
extension obtains the public daily-time estimate and asks the broker to combine
it with the live grant.

The GTK feedback worker sends an explicitly submitted report directly over
HTTPS. The broker only supplies validated diagnostics; it does not upload
feedback. The separately deployed portal owns delivery and retention. Its
generic multipart contract and the client's retry rules are described in
[Logging and feedback](SystemDesign/Logging-and-Feedback.md#multipart-and-retry-contract).

A trusted Polkit agent authenticates the selected administrator. Product front
ends never handle the administrator password.
Normal management, approval and enforcement use local services. Only explicitly
opened online links and submitted feedback require Internet access; the broker's
service sandbox permits Unix sockets, not Internet sockets.

## State ownership and shared constraints

Root-owned per-child preferences hold durable parent choices; missing records
use defaults. AccountsService holds the live app blocklist, limit type, daily
limit and one-time grant. Malcontent owns measured usage. The broker derives
UID-scoped fapolicyd execution rules from live filters and saved patterns, and
controls per-account activation of the packaged GNOME extension. Runtime grants,
usage, and generated rules are never imported into preferences.

Request duration/custom value and soft-app choice are shared per child. Actual
child/approver selector defaults are user-local, non-authoritative UI state;
the kiosk and each child overlay may remember different approvers. Separate
saved mute fields remain in the schema, while sound/lightning and their control
are disabled in the current request UI. The child panel's right-click countdown
animation preference is a separate per-user GSettings value, defaults to false,
and has no policy authority. Feedback drafts, attachment bytes and retry
submissions live only in frontend memory. Removal/purge do not reset ordinary
users' selector files or countdown-animation setting.

- Screen-time control and saved app policy are independent. Temporary approval
  can relax soft blocks while preserving hard blocks.
- Exhausting total usable time locks the child session. An expired grant alone
  does not require locking while daily time remains. Expiry does not itself
  terminate applications; app-policy transactions and session reconciliation own
  that behavior.
- Running-app enforcement targets only the selected child's verified processes.
- Reversible writes are read back and rolled back on failure. Termination is
  irreversible: once apps may have closed, failures retain stricter policy;
  approval/revocation restore prior time values. These are not unconditional
  all-or-nothing transactions.
- Structured diagnostics accept only catalogue-approved events and fields at
  production, storage, export and transmission boundaries. Arbitrary text and
  unknown fields are rejected, not automatically made safe by redaction.
  Call-site provenance review still prevents personal data entering otherwise
  permitted fields.

The successful mutation paths have different effects; retaining a time grant
does not imply retaining its soft-app exception:

| Operation | One-time grant | Live app policy | Running apps owned by the selected child |
| --- | --- | --- | --- |
| Turn screen-time control on or off | Cleared on the toggle transition | Complete saved hard and soft blocks | No termination |
| Edit the allowance while control stays on | Preserved | Complete saved blocks | No termination |
| Save app policy | Unchanged | Complete newly saved blocks | Terminate newly blocked targets/patterns and soft-to-hard transitions |
| Approve with soft apps excluded | Replace using the request calculation | Complete saved blocks | Terminate all matching blocked apps before writing the grant |
| Approve with soft apps included | Replace using the request calculation | Hard blocks only | No termination, including already-open hard-blocked apps |
| Revoke | Cleared, including an already empty grant | Complete saved blocks | Terminate all matching blocked apps; daily time is unchanged |
| Grant expires naturally | Expired record remains | No immediate product filter write | No termination; lock only when total usable time is exhausted |
| Prepare session with a nonzero expired grant | Expired record remains | Complete saved blocks | Terminate all matching blocked apps |
| Prepare session with an active grant or zero-duration record | Unchanged | Unchanged | No termination |

The broker's revocation method does not require an active grant. The Parent
button uses its last loaded positive **total** remaining time and idle state,
so daily-only time can make it available. Failure/rollback behavior is specified
in [Broker transactions](SystemDesign/Broker.md#authorization-and-grant-transactions).

## Runtime flows and verification limits

The Parent App serializes its automatic saves. Allowance editing is enabled only
while screen-time control is on. Its remaining-time explanation always shows
both daily and grant balances, including zero values. Child discovery refreshes
while Parent stays open; the app catalogue instead loads on child selection and
needs reselection or a new Parent window to display newly installed/removed
launchers. Saving policy still resolves current targets at the broker.
Saved custom wildcard rules restore in the UI; an explicit precise override
for an app with a suggested wildcard currently redisplays that default on
preference reload, including failed-save recovery, and can be overwritten by a
later app-policy save. See the
[frontend limitation](SystemDesign/Frontends.md#parent-controls-and-shared-information).

The broker's nonblocking shared transaction lock covers app-policy saves,
approvals, revocations and session preparation; `SetParentControl` and
request-choice persistence do not take that
lock. Approval revalidates its preference snapshot around authentication and
usage queries. The installed request forms disable requests for a child whose
control is off; the broker enforces that condition for `RequestOwnAccess`, but
its kiosk-only `RequestAccess` can initialize live time limits without changing
the saved toggle or enabling the child extension. UI availability and D-Bus
authorization are therefore separate contracts.

Request-form readiness also differs from duration validity: an invalid custom
value leaves Request enabled when the form is otherwise ready. The form shows
validation feedback and refuses that submission before saving or authenticating.

Fixed requests add time to the greater of daily remaining and grant remaining.
Rest-of-day instead replaces the grant with the interval to local midnight.
Grant issuance is timestamped before commit/termination finishes; it is not
paused until the child next uses the desktop. On startup and unlock, the child
requests broker reconciliation asynchronously. A nonzero expired grant restores
strict app policy; a current grant or zero-duration record is a no-op. This
is not a compositor barrier preventing all desktop use before reconciliation.

Broker startup reconciles live AccountsService filters, reasserts enabled
extensions, and attempts existing graphical-session runtime-cap cleanup before
registering its D-Bus object. It does not replay every saved preference into
AccountsService. Separately, display-manager startup requires fapolicyd's boot
canary readiness. GDM does not have a broker-readiness dependency.

Each broker filter write synchronously reconciles native rules, compiling and
requesting a rules-only reload unless its successful-notification cache permits
reuse. Successful commands and account read-back do not acknowledge the daemon's
exact active policy generation. The probe
support modules and deferred generation-witness design in
[Application policy](SystemDesign/Applications.md#generation-witness-design-gate)
are not wired into the production policy adapter's commit path. Keep those
limits distinct from observed installed allow/deny behavior and from the
initial boot canary.

## Diagnostics and customer acceptance

The broker is the sole structured event-file writer under
`/var/log/oh-no-parent-control/<component>/YYYY-MM-DD.events`. Rotations and
incident context are bounded. The export contains validated readable `.log`
files and `system-info.json`, not raw legacy text logs or journals. Parent,
child and kiosk roles may export the same four-component report. Frontends add
reviewed system information; download and Send share the prepared snapshot.
The kiosk hides file choosers and external links while retaining in-app error
reporting. Opening feedback never uploads anything.

The [scenario catalogue](../tests/e2e/scenarios.json) declares installation,
account discovery, policy editing, time exhaustion, both approval surfaces,
launch routes, retained sessions, lifecycle persistence, updates/removal, About
and feedback. Injected-fault and internal-state obligations remain in the
separate system-test queue, outside the UI scenario inventory. Follow the
[E2E building blocks](TestAutomation/E2E-Building-Blocks.md)
for public UI actions and observations; source review, scenario declarations,
and local unit/component checks do not establish completed customer acceptance.
The [customer recipes](TestAutomation/E2E-Scenario-Recipes.md) bind each scenario
to public actions, finite inputs and observable results, including child panel
preferences, daily-only revocation, account changes and natural day boundaries.
They also cover approval after a decision delay, temporary app access by launch
route, and bounded repeated work/game routines with independent child state.
Those histories observe each intermediate result through the public interfaces;
switching away and returning is an action that can itself restore app blocks.
The [inventory reconciliation](TestAutomation/E2E-Building-Blocks.md#inventory-reconciliation)
retains displaced engineering assertions and deferred interactive mute separately.
Scenario declarations and documentation do not qualify an unimplemented route
or establish installed acceptance.

## Package removal lifecycle

See [Package removal](SystemDesign/Package-Removal.md) for cleanup, ownership,
rollback, purge, and reboot notices.

## Maintaining the design

Update details in their owning module; update this master when boundaries,
shared constraints, or reading routes change. Keep modules understandable with
this overview and link to specific sections for additional context. Implementation
entry points belong in modules; the [Makefile](../Makefile) owns the complete
build and installation map.

Use the current production entry points, validators and package activation
classifier to resolve descriptive mismatches. Keep future designs explicitly
deferred and retain existing test obligations; aligning documentation alone
does not change executable expectations or establish a passing release.

Follow [Package update](Publishing.md#package-update-activation) for changed system integration and
[Data migration](SystemDesign/Data-Migration.md) before incompatible saved-data changes.
Consult [E2E building blocks](TestAutomation/E2E-Building-Blocks.md) for validation workflows and the
[threat model](Threat-Model.md) for security targets and remaining verification;
those targets are distinct from the current implementation described here.
