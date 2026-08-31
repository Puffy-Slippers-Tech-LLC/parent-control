# Oh No! Parent Control — Kiosk Request Station Execution Plan

## 1. Purpose

Add a dedicated, unrestricted GNOME Kiosk session in which a child can select
their local standard account, request additional time, and choose whether
soft-blocked apps remain available. A child account's in-session GNOME Shell extension remains a
separate supported request path.

The finished request flow must show exactly one administrator authentication
dialog. It must use supported GNOME, Polkit, D-Bus, AccountsService, and
Malcontent interfaces. It must not patch or inspect private GNOME Shell objects.

This document is the standalone implementation plan. A coding agent starting
with only this repository and this document should be able to implement and
validate the kiosk design.

The product is still under development and has no deployed users. Do not build
data converters, account migrations, or upgrade paths. Keep kiosk and
in-session extension policy/authorization boundaries explicit rather than
silently coupling their stores.

## 2. Target and verified platform contracts

Target platform:

- Ubuntu 26.04;
- GNOME 50;
- Wayland;
- GNOME Kiosk 50;
- Polkit 127; and
- Malcontent 0.14.

The target installation exposes these supported AccountsService vendor
extensions:

- `com.endlessm.ParentalControls.SessionLimits`;
- `com.endlessm.ParentalControls.SessionLimits.ActiveExtension`, type `(tu)`;
- `com.endlessm.ParentalControls.AppFilter`;
- `com.endlessm.ParentalControls.AppFilter.AppFilter`, type `(bas)`.

`ActiveExtension` is `(grant_time, duration_seconds)`. Its effective end is the
sum of those values. A new value replaces the previous extension; it does not
add to the remaining time.

`AppFilter` is `(allowlist, targets)`. This product uses a blocklist, so
`allowlist` must be `false` and `targets` must contain the configured Flatpak
application IDs and absolute executable paths.

GNOME Kiosk is the supported fixed-purpose compositor/session. It runs one
application full-screen without the GNOME desktop shell, panel, overview, dash,
or lock-screen internals.

Before coding, verify these contracts against the installed target packages and
installed D-Bus introspection XML. If a target package differs from the versions
above, record the difference and stop before silently adapting the design to an
unverified interface.

## 3. User-visible workflow

The device has a dedicated request-station account and zero or more managed
standard accounts:

1. A **managed account** is a local standard desktop account. Malcontent
   session limits and app filters apply after its first approved request.
2. The **request-station account** runs only the GNOME Kiosk request
   application. It has no Malcontent time limit.

Expected flow:

```text
Child account reaches its time limit
    -> GNOME locks or denies the child session normally
    -> child switches to the request-station account
    -> GNOME Kiosk shows only Oh No! Parent Control
    -> child selects their local standard account
    -> child selects a duration
    -> child chooses whether soft-blocked apps are allowed
    -> child presses Request
    -> one standard Polkit administrator dialog appears
    -> parent authenticates once
    -> broker updates the child account
    -> kiosk application reports success and exits
    -> GDM is shown
    -> child returns to the normal child account
```

The request-station login may use a child-known password. That login is not an
administrator authorization and is not counted as the request's Polkit dialog.
Do not weaken the child account's authentication or the administrator account's
authentication to simplify this flow.

## 4. Required architecture

```text
Request-station account (unprivileged, unlimited)
  GNOME Kiosk 50
    Oh No! Parent Control GTK application
      |
      | system D-Bus: RequestAccess(target_uid, duration_seconds, allow_soft_blocked_apps)
      v
Root-owned request broker
      |
      | one interactive CheckAuthorization
      v
Polkit + the kiosk session's standard authentication agent
      |
      | approved once
      v
Revalidated local standard AccountsService user object
      +-- SessionLimits.LimitType / DailyLimit (first use only)
      +-- AppFilter.AppFilter
      +-- SessionLimits.ActiveExtension
```

Use a privileged broker rather than granting the kiosk application temporary
`ChangeAny` permissions. The broker exposes only the product operation,
enumerates eligible accounts itself, revalidates the selected account before
and after authorization, validates the duration and root-owned policy, performs
exactly one Polkit check, and then carries out the bounded writes as root.

This is a normal supported Polkit service design. The broker must not replace
Polkit, implement password entry, inspect authentication secrets, or draw its
own authentication dialog.

## 5. Explicit non-goals and forbidden techniques

The kiosk implementation must not implement or retain any of the following:

- `unlock-dialog` extension code;
- a custom button inside `ParentalControlsShield`;
- access to `AuthPrompt`, `UnlockDialog`, `Main.screenShield`, or private Shell
  fields;
- patches to GNOME Shell's Polkit agent;
- patches to `TimeLimitsManager` or `_estimatedTimes`;
- synthetic lock-screen dialogs;
- Malcontent database or policy-file edits;
- AccountsService database edits;
- PAM bypasses;
- a custom password or administrator-authentication system;
- an unrestricted privileged method which accepts an arbitrary UID, arbitrary
  property name, or arbitrary D-Bus payload; or
- a normal desktop session for the request-station account.

The normal child account remains governed by stock GNOME and Malcontent. The
new software only submits an authenticated extension/filter operation from a
separate active session.

## 6. Security and trust boundaries

Treat the child and request-station accounts as untrusted. Treat these as the
trusted computing base:

- root-owned broker executable and service definition;
- root-owned Polkit action;
- root-owned D-Bus policy;
- root-owned product configuration and hard/soft app policy;
- stock Polkit authentication agent; and
- stock AccountsService and Malcontent components.

The button is not an authorization boundary. The broker must remain safe if an
untrusted process calls its D-Bus method directly.

The broker must therefore enforce all of the following independently of the
UI:

- the D-Bus caller is the configured request-station UID;
- the target UID resolves through AccountsService to a local, non-system,
  non-administrator standard account;
- the target and kiosk UIDs differ and the target UID is at least 1000;
- the target identity and account type are unchanged after authorization;
- the duration is either the rest-of-day sentinel or within the supported custom range;
- the app-access choice is a boolean and never supplies filter targets;
- every app-filter target has the expected Flatpak-ID or absolute-path form;
- only one request is processed at a time;
- a bounded rate limit prevents authentication-dialog flooding;
- cancellation and denial cause no writes;
- authorization is checked for the real D-Bus sender, not for the root broker;
  and
- the broker never accepts caller-supplied Polkit action IDs or target object
  paths.

The Polkit action defaults must require an administrator for active, inactive,
and other callers. Do not use `yes`, `allow`, `auth_self`, or a rule that grants
the action merely because the request-station session is active.

The request-station account must not be a sudoer or administrator and must not
own or modify installed application, service, policy, session, or configuration
files.

## 7. System identities and configuration

Install a root-owned configuration file, for example:

```text
/etc/oh-no-parent-control/config.json
```

Required logical schema:

```json
{
  "version": 2,
  "kiosk_uid": 991,
  "app_filter": {
    "hard_blocked_targets": ["org.example.Game"],
    "soft_blocked_targets": ["/usr/bin/example-game"]
  },
  "minimum_request_interval_seconds": 5
}
```

The UID above is an example, not a default. Provisioning resolves only the
kiosk account. Managed accounts are discovered at runtime and are never stored
in installation configuration.

The broker always derives a complete blocklist from this root-owned policy.
Hard-blocked targets are always included; soft-blocked targets are omitted only
when the request's `allow_soft_blocked_apps` value is true.

For the zero rest-of-day sentinel, calculate the positive number of seconds from the approval
time to the next local midnight. Perform this calculation in the broker after
authorization so time spent in the dialog is not subtracted from the grant.
Reject a zero, negative, overflowed, or unexpectedly long result.

The configuration parser must reject unknown keys where ambiguity would be
unsafe, malformed types, duplicate logical choices, invalid UIDs, invalid
targets, and insecure ownership or permissions. Fail closed and log the reason.

## 8. Broker service contract

Create a root-owned, system-bus-activated service with a stable product-owned
name, such as:

```text
Bus name:   com.puffyslippers.OhNoParentControl1
Path:       /com/puffyslippers/OhNoParentControl1
Interface:  com.puffyslippers.OhNoParentControl1
```

Keep the public surface minimal:

```text
ListManagedUsers() -> (
    users: a(us)
)

RequestAccess(
    target_uid: u,
    duration_seconds: u,
    allow_soft_blocked_apps: b
) -> (
    correlation_id: s,
    result_code: s
)
```

The duration list is a shared application asset also consumed by the in-session
dialog. Define a small stable set of result codes, including `approved`,
`denied`, and `cancelled`; use stable
D-Bus error names for invalid requests and service failures.

Do not return authentication secrets or detailed internal policy state.

`ListManagedUsers` freshly enumerates NSS account candidates, then returns only
eligible UIDs and display labels whose metadata is validated through
AccountsService. Do not use `AccountsService.ListCachedUsers`, which is
intentionally non-exhaustive and may omit a newly created account before its
first login. `RequestAccess` must re-resolve and revalidate its selected UID,
duration, and boolean, then use the broker's freshly loaded policy; it must
never accept app targets or account metadata from the client.

The system-bus policy should allow only the configured request-station account
to call the methods. The broker must still verify the sender credentials at
runtime because bus policy is defense in depth, not application validation.

### 8.1 Polkit action

Define one action, for example:

```text
com.puffyslippers.OhNoParentControl1.request-access
```

Its message should clearly say that an administrator is authorizing additional
time and, when selected, replacement of the child's app restrictions. Set all
three defaults to `auth_admin`. Do not use `auth_admin_keep`: no authorization
must survive this single broker check. No implied permissions are necessary
because the authorized broker performs the AccountsService writes as root.

Call `CheckAuthorization` once with interactive authorization allowed and with
a subject derived from the request's unique system-bus sender. Never authorize
the broker's PID or UID as the subject. Treat challenge cancellation, denial,
agent disappearance, caller disconnect, and timeout as denial.

Do not perform a second interactive authorization under any error or retry
path. A failed request returns to the UI and requires a new explicit click.

### 8.2 Applying the requested change

After the single successful authorization:

1. Re-resolve the selected UID and confirm it is the same eligible local
   standard account shown before authorization.
2. Read and validate the current values needed for rollback.
3. Set `DailyLimit` to zero; if `LimitType` is zero, enable its daily-limit
   flag. This establishes the product's grant-only model.
4. Derive and write the complete hard/soft blocklist as
   `AppFilter = (false, targets)`.
5. Write `ActiveExtension = (approval_time, duration_seconds)` last.
6. Read all changed values back and verify exact equality.
7. Return success only after verification.

Writing `ActiveExtension` last prevents granting time when the requested filter
could not be applied. If the filter write succeeds but a later step fails,
restore its previous value and verify the restoration. Report a distinct
high-severity error if rollback cannot be verified.

The AccountsService properties do not provide a cross-property transaction.
The implementation supplies best-effort transactional behavior through
ordering, read-back verification, and rollback. Document this limitation in
operator-facing diagnostics without exposing it as a second authorization
prompt.

## 9. Kiosk application

Implement a normal GTK 4/libadwaita application suitable for GNOME Kiosk. It
must not import `resource:///org/gnome/shell/...`, use Shell extension APIs, or
run inside GNOME Shell.

The application has two views:

1. **Request:** an eligible-account selector with refresh, the shared duration
   choices, soft-block toggle, and Cancel/Request buttons.
2. **Result:** approved, denied/cancelled, or unavailable, plus Return to Login.

Required behavior:

- load duration choices from the same installed asset as the Shell dialog;
- default to 30 minutes and disallow soft-blocked apps;
- show the exact target account's administrator-configured display label;
- disable controls while a request is in flight;
- issue only one `RequestAccess` call per Request click;
- never retry automatically after a Polkit denial or D-Bus failure;
- never draw password fields or collect authentication input;
- redact low-level D-Bus details from the child-facing error view;
- log a request correlation ID, duration, soft-app choice, and outcome, but no
  password, token, or authentication-agent data; and
- quit cleanly when Cancel or Return to Login is selected.

Request invokes the standard Polkit dialog directly. The Polkit dialog
establishes administrator identity and the kiosk never renders password fields.

## 10. Kiosk session and authentication agent

Use the distribution's GNOME Kiosk package and its documented session-launch
mechanism. Install a root-owned kiosk session definition which starts:

1. a maintained distribution Polkit authentication agent; and
2. the Oh No! Parent Control application.

The authentication agent must register for the active kiosk session and render
the one administrator dialog produced by the broker's Polkit check. Do not
embed a Polkit agent in the application unless the distribution provides no
maintained agent; if that fallback appears necessary, stop and revise this
design before implementing authentication UI.

Exiting the application must end the kiosk session through the supported kiosk
session lifecycle and return to GDM. Do not invoke private GDM or GNOME Shell
methods.

### 10.1 Mandatory session-escape gate

The request-station account is unrestricted by time limits, so it must never be
able to start a normal GNOME desktop session. Before considering the design
deployable, prove on the target image that system configuration can restrict
that account to the kiosk session using supported display-manager/session
mechanisms.

Test at minimum:

- initial login;
- logout and login again;
- reboot;
- switch-user from the child session;
- session chooser/gear menu;
- recovery from application crash;
- common keyboard shortcuts;
- virtual-terminal switching;
- file chooser and URI handling;
- accessibility shortcuts;
- D-Bus activation; and
- attempts to launch a terminal or another desktop application.

If GDM allows the request-station account to select a normal desktop and no
supported per-account restriction exists, this is a release blocker. Do not
paper over it with private Shell patches. Choose a supported dedicated
seat/virtual-terminal kiosk deployment, or require an upstream/distro session
restriction mechanism, and update this plan before proceeding.

Kiosk UI minimalism alone is not proof of confinement.

## 11. Child-session refresh behavior

After `ActiveExtension` changes, supported Malcontent behavior should publish
the updated estimate and GNOME should leave its limit-reached state. Do not
restore the old private `_estimatedTimes` overlay or call private manager
methods.

Validate all of the following in a booted GNOME/GDM VM with a working system
bus:

- the supported change notification is emitted promptly;
- a child session left running while switching to the kiosk observes the new
  extension when switching back;
- a fresh child login observes the extension;
- a shorter grant replaces a longer grant;
- expiry returns the account to the exhausted state; and
- Shell or session restart does not extend or shorten the approved duration.

If the existing child session does not refresh through supported signals, the
supported product behavior must require ending that child session and logging
in fresh. A private Shell cache patch is not an acceptable fallback.

## 12. App-filter semantics and limitations

Every approved request replaces the complete configured `AppFilter` blocklist
for the child. It is not a delta and must not be merged with the live value.
Hard-blocked targets always remain blocked. The toggle controls only whether
soft-blocked targets are included.

Do not promise that changing an app filter terminates an application which is
already running in the suspended child session. Validate actual enforcement on
return to the child account. If already-running blocked applications remain
usable, either require a fresh child login for filter-changing requests or
state and test the narrower supported behavior.

## 13. Repository layout and shared behavior

The repository ships two intentional request paths: the existing in-session
GNOME Shell extension for the child account, and the kiosk product. Preserve
the extension's build/install artifacts and its existing policy. The kiosk path
must remain independent of private Shell objects and use its own broker action.

Reuse only neutral presentation and request-choice logic where practical. Do
not reuse the extension's user-writable policy/preferences, temporary grants,
or combined `ChangeOwn` authorization in the kiosk broker; root-owned kiosk
configuration and the single broker Polkit check are separate security
boundaries.

Suggested new layout:

```text
app/                         unprivileged GTK kiosk application
broker/                      root system-bus service
config/                      schema and example product configuration
data/
  dbus-1/system.d/           broker call policy
  dbus-1/system-services/    D-Bus activation
  polkit-1/actions/          single request-access action
  systemd/                   broker/session units if required
  wayland-sessions/          GNOME Kiosk session definition if required
tests/
  unit/
  integration/
docs/
  System-Design.md           this execution plan
```

Use distribution-supported runtime libraries. Keep the dependency set small
and make all installed paths explicit in the build/install tooling.

## 14. Execution phases

Complete the phases in order. Do not begin private-API work if a supported
contract fails; report the failed gate instead.

### Phase 0 — Record baseline and protect repository work

- Inspect `git status` and preserve unrelated changes.
- Run the existing checks and record their result.
- Identify any reusable policy parsing, app catalog, D-Bus serialization, and
  tests separately from Shell-specific code. Reuse is optional and must not
  constrain the new architecture.
- Record installed target package versions.

Deliverable: a short reuse/removal inventory and reproducible baseline command.

### Phase 1 — Prove platform prerequisites

- Install or inspect GNOME Kiosk and its packaged session launch files.
- Identify the maintained Polkit authentication agent available on Ubuntu.
- Inspect installed AccountsService/Malcontent introspection XML.
- Build a throwaway kiosk session which displays one harmless GTK window.
- Confirm a test Polkit action opens exactly one dialog in that session.
- Prove the mandatory session-escape gate in section 10.1.

Deliverable: evidence for kiosk confinement, Polkit-agent operation, and exact
installed interface signatures. Stop if confinement cannot be achieved using
supported mechanisms.

### Phase 2 — Define packaging and configuration

- Add the configuration schema and strict validator.
- Add provisioning logic for the kiosk UID only.
- Ensure the kiosk account has `SessionLimits.LimitType = 0`.
- Add root-owned installation paths, ownership, and modes.
- Add clean-install and uninstall behavior. Uninstall must not delete system
  accounts or managed-account policy unless the administrator explicitly requests that
  separate destructive action.

Deliverable: install into a disposable prefix/image and verify permissions.

### Phase 3 — Implement the broker

- Export the minimal D-Bus interface.
- Verify D-Bus sender UID on every call.
- Implement request serialization and rate limiting.
- Implement one interactive Polkit check for the real sender.
- Enumerate and revalidate only eligible AccountsService user objects.
- Implement filter-first and extension-last writes.
- Add read-back verification and filter rollback.
- Add structured, redacted logging and stable error names.

Deliverable: broker unit tests with mocked Polkit and AccountsService plus
system-bus integration tests in a disposable VM.

### Phase 4 — Implement the kiosk application

- Build the Request, Review, and Result views.
- Load options only from the broker.
- Make request submission single-flight.
- Handle cancellation, denial, timeout, broker restart, and malformed replies.
- Ensure Return to Login ends the kiosk session cleanly.

Deliverable: application tests and a working full-screen kiosk session without
privileged writes.

### Phase 5 — End-to-end authorization

- Connect the application to the real broker and Polkit agent.
- Count visible authentication dialogs for approval, denial, cancellation, and
  backend failure paths.
- Verify the app never handles secrets.
- Verify both writes use the supported AccountsService interfaces.

Deliverable: video or timestamped logs demonstrating exactly one Polkit dialog
for a combined approved request.

### Phase 6 — Child-session and enforcement validation

- Test requests with soft-blocked apps disallowed.
- Test requests with soft-blocked apps allowed.
- Test shorter-over-longer replacement.
- Test expiration and next-day behavior.
- Test switch-back to an existing child session and fresh login.
- Test already-running blocked applications.
- Test crash and power-loss points between the two writes.

Deliverable: completed integration matrix and documented supported recovery
behavior.

### Phase 7 — Release both supported request paths

- Keep the GNOME Shell extension in build and release artifacts.
- Keep private Shell adapters strictly confined to that extension; verify the
  kiosk app and broker contain no private Shell imports or references.
- Update README and operator documentation for the extension plus kiosk
  provisioning, entry, recovery, and uninstall.
- Do not add migration scripts, configuration readers, or authorization
  compatibility modes between the two paths.

Deliverable: a package containing the independently tested extension and kiosk
architectures.

## 15. Required automated tests

At minimum, cover:

- strict configuration validation and secure-file checks;
- caller UID mismatch;
- kiosk, root, administrator, system, remote, and low-UID target rejection;
- root/admin/system target rejection;
- out-of-range durations and malformed boolean values;
- local-midnight boundary, DST transition, and clock edge cases;
- invalid Flatpak IDs and executable paths;
- concurrent request rejection;
- request rate limiting;
- Polkit approval, denial, cancellation, timeout, and agent loss;
- caller disconnect during authorization;
- confirmation that each click invokes `CheckAuthorization` once;
- no property writes before approval;
- filter omitted;
- filter written before extension;
- extension failure followed by successful filter rollback;
- rollback failure escalation;
- exact read-back verification;
- broker restart and malformed D-Bus calls; and
- UI single-flight and error redaction.

Tests must never modify the developer's real AccountsService user objects.
Integration tests require disposable users in a VM or disposable system image.

## 16. Manual acceptance matrix

The release candidate must pass all of these on the target image:

| Scenario | Expected result |
| --- | --- |
| Kiosk account starts | Only the request application is usable |
| Kiosk account time state | No Malcontent time limit applies |
| Alternative session attempt | Normal desktop cannot be started for kiosk UID |
| Cancel before authorization | No Polkit dialog and no writes |
| Parent cancels Polkit | One dialog, no writes |
| Wrong administrator password | Same standard dialog handles retry; app creates no second request |
| Soft apps disallowed | One dialog; hard and soft targets are blocked |
| Soft apps allowed | One dialog; only hard targets are blocked |
| App-filter write failure | No extension is granted |
| Extension write failure | Prior filter is restored and verified |
| Repeated Request clicks | One in-flight request and one dialog |
| Switch back to child | Approved duration is recognized |
| Grant expires | Stock Malcontent enforcement resumes |
| Broker unavailable | Redacted error; kiosk remains confined |
| App crashes | Session exits or safely restarts into the same kiosk app |
| Reboot | Identities, confinement, configuration, and enforcement persist |

Count a Polkit agent's internal wrong-password retry as part of the same dialog,
not as a second application authorization request.

## 17. Observability and privacy

Use a consistent prefix or structured journal identifier:

```text
[oh-no-parent-control]
```

Log:

- correlation ID;
- caller UID;
- selected target UID;
- duration seconds and soft-app choice;
- authorization outcome;
- each property-write and verification stage;
- rollback attempt and outcome; and
- final stable result code.

Never log:

- passwords;
- authentication-agent responses;
- Polkit temporary authorization data;
- full user-provided D-Bus payloads;
- unrelated account information; or
- more personal information than numeric UIDs required for diagnosis.

## 18. Definition of done

The replacement is complete only when:

- [ ] Deployment succeeds without any managed account present.
- [ ] The kiosk account is not subject to a session time limit.
- [ ] The kiosk account cannot enter a normal desktop session.
- [ ] GNOME Kiosk shows only the request application.
- [ ] A supported maintained Polkit agent serves the kiosk session.
- [ ] The broker authenticates the real D-Bus caller exactly once.
- [ ] The child cannot approve a request without administrator credentials.
- [ ] The broker can target only a currently eligible local standard account.
- [ ] Accounts created after deployment appear after refreshing the selector.
- [ ] Time-only requests leave the app filter unchanged.
- [ ] Combined requests replace the configured filter and extension correctly.
- [ ] Failures cannot grant time without the selected filter.
- [ ] Read-back and rollback behavior are tested.
- [ ] Existing and fresh child sessions observe the extension through supported
      behavior.
- [ ] Expiry restores stock Malcontent enforcement.
- [ ] The kiosk application and broker import, patch, and inspect no private
      GNOME Shell API.
- [ ] The child in-session extension remains shipped and independently tested.
- [ ] No custom authentication dialog or secret handling exists.
- [ ] Automated tests and the manual acceptance matrix pass on Ubuntu 26.04.
- [ ] Installation, provisioning, recovery, logging, and uninstall are
      documented for an operator starting from a clean machine.

## 19. Stop conditions

Stop implementation and report the blocker rather than weakening the design if:

- the kiosk UID can select or escape into a normal desktop session;
- no maintained authentication agent works in GNOME Kiosk;
- Polkit cannot authenticate the actual kiosk D-Bus sender;
- the target AccountsService properties differ from the verified signatures;
- the child session cannot recognize a supported `ActiveExtension` update even
  after a fresh login;
- app-filter enforcement is materially weaker than the UI promise; or
- exactly one authentication dialog cannot be demonstrated.

The acceptable response to a stop condition is a supported distro/upstream
integration change or a documented product requirement change. Do not
introduce private GNOME Shell integration into the kiosk path as a fallback;
the existing in-session extension remains separately scoped.
