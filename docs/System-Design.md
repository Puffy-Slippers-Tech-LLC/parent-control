# System design

Oh No! Parent Control has three unprivileged front ends around one privileged
system D-Bus broker. The broker owns runtime product policy and cross-account
writes. Operating-system services provide enforcement behind that boundary.

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
| Parent GTK app (`parent/`) | Administrator policy management and grant revocation |
| Child GNOME Shell extension (`child/`) | Countdown, expiry lock, and request-overlay launcher; no independent settings UI |
| Shared GTK request form (`kiosk/`) | Child overlay and dedicated request-only kiosk session; GUI changes must work in both |
| Root broker (`broker/`) | Caller validation, policy, storage, approval transactions, and OS adapters |

Front ends call the broker over system D-Bus. It derives caller identity from
bus credentials and revalidates roles, targets, and request inputs before
privileged writes. Front ends access private preferences only through the
broker. The parent additionally reads usage and the current AccountsService
grant directly with its own system-bus identity, and sends optional feedback
over HTTPS. Those reads and reports confer no policy-writing authority.

A trusted Polkit agent authenticates the selected administrator. Product front
ends never handle the administrator password.

## State ownership and shared constraints

Root-owned per-child preferences hold durable parent choices; missing records
use defaults. AccountsService holds the live app blocklist and one-time grant.
Malcontent owns measured usage. The broker derives UID-scoped fapolicyd execution
rules from live filters and saved patterns, and controls per-account activation
of the packaged GNOME extension. Runtime grants, usage, and generated rules are
never imported into preferences.

- Screen-time control and saved app policy are independent. Temporary approval
  can relax soft blocks while preserving hard blocks.
- Expiry locks the child session. It does not itself terminate applications;
  app-policy transactions and session reconciliation own that behavior.
- Running-app enforcement targets only the selected child's verified processes.
- Logging call sites must exclude PII and secrets; the file writer does not
  automatically redact arbitrary text.

## Package removal lifecycle

See [Package removal](SystemDesign/Package-Removal.md) for cleanup, ownership,
rollback, purge, and reboot notices.

## Maintaining the design

Update details in their owning module; update this master when boundaries,
shared constraints, or reading routes change. Keep modules understandable with
this overview and link to specific sections for additional context. Implementation
entry points belong in modules; the [Makefile](../Makefile) owns the complete
build and installation map.

Follow [Package update](Publishing.md#package-update-activation) for changed system integration and
[Data migration](SystemDesign/Data-Migration.md) before incompatible saved-data changes.
Consult [Test automation](Test-Automation.md) for validation workflows and the
[threat model](Threat-Model.md) for security targets and remaining verification;
those targets are distinct from the current implementation described here.
