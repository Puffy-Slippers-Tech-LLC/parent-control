# Oh No! Parent Control functional specification

This specification defines the behavior required for release acceptance on a clean, supported Ubuntu 26.04 Desktop computer. Visual styling, animation, spacing, and other presentation details are outside its scope. A release is accepted only when every applicable statement below is true.
Audience does not need to understand the technical internals. An end user must be able to follow through and validate the app.

Terms used below:

- **Child**: a local, non-administrator account managed by the product.
- **Parent**: a local administrator who configures or approves access.
- **Daily allowance**: the child's configured screen time for the current local day.
- **One-time grant**: additional access approved by a parent.
- **Hard blocked app**: an app that only a parent can unblock in the Parent App.
- **Soft blocked app**: an app that may be included in an approved one-time grant.

## 1. Core end-to-end release acceptance

### Accounts and access

- [ONPC-CORE-ACCOUNTS-001] The Parent App is available to local administrators. A standard user cannot open it or perform management actions by launching it another way.
- [ONPC-CORE-ACCOUNTS-002] The Parent App and request station discover current local, interactive, non-administrator accounts, including accounts created after installation. Administrator, system, remote, and dedicated request-station accounts are never offered as children.
- [ONPC-CORE-ACCOUNTS-003] An approving parent must be a current, unlocked, local, interactive administrator. Ineligible accounts are not offered and cannot approve a request by another route.
- [ONPC-CORE-ACCOUNTS-004] Each child's settings and grants are independent. Managing or granting access to one child does not alter another child, an administrator, or an unrelated user.

### Screen-time setup and enforcement

- [ONPC-CORE-TIME-001] A parent can enable or disable screen-time control separately for each child and set a daily allowance from 0 minutes through 24 hours.
- [ONPC-CORE-TIME-002] An allowance of 0 minutes is grant-only mode: the child has no daily time and can use the account only while a one-time grant is active.
- [ONPC-CORE-TIME-003] Enabling screen-time control activates the packaged child-session component for that child, including in an existing retained session, applies the saved daily allowance, clears stale one-time access, and applies the child's saved app rules.
- [ONPC-CORE-TIME-004] Changing an enabled daily allowance takes effect immediately without shortening or deleting a current one-time grant. Saved app rules are reapplied so a previous temporary soft-app exception cannot become permanent.
- [ONPC-CORE-TIME-005] Disabling screen-time control removes the daily restriction, deactivates the child-session component for that child, and clears one-time access. The selected allowance and app rules are retained for later use. App rules remain enforced while screen-time control is disabled.
- [ONPC-CORE-TIME-006] When screen-time control is enabled, the Parent App shows the child's current remaining time for today and keeps it reasonably current. It distinguishes unused daily time from an active one-time grant and shows the resulting usable time. If the status cannot be read after retries, it is shown as unavailable rather than guessed.
- [ONPC-CORE-TIME-007] With screen-time control enabled, the child can sign in or unlock while usable time remains. On session entry the child component asks the broker to reconcile any expired grant before normal use, then shows the remaining time in the desktop panel. The display counts down by minutes, then by seconds during the final minute.
- [ONPC-CORE-TIME-008] When an enabled child's usable time reaches zero, the active desktop locks. If that retained desktop is unlocked without new time, it locks again. A fresh child login is denied until daily time or a one-time grant is available. GDM explains that the account's time limit has passed instead of reporting a password-authentication failure.
- [ONPC-CORE-TIME-009] Expiry locks only the managed child's desktop; it does not terminate the live session or end another user's foreground session.
- [ONPC-CORE-TIME-010] A valid one-time grant permits both unlocking the retained child session and starting a new child login for the granted interval.
- [ONPC-CORE-TIME-011] Daily usage and a “Rest of the day” grant follow the computer's local day. “Rest of the day” expires at the next local midnight, including on daylight saving time transition days.

### Application access

- [ONPC-CORE-APPS-001] The Parent App lists launchable apps available to the selected child, including supported system apps and apps installed only for that child. It does not substitute the administrator's app list.
- [ONPC-CORE-APPS-002] Every listed app has one access rule:

  - [ONPC-CORE-APPS-003] **Always Allowed**: the product does not block the app.
  - [ONPC-CORE-APPS-004] **Hard Blocked**: the app remains blocked until a parent changes its rule. A time request can never allow it.
  - [ONPC-CORE-APPS-005] **Soft Blocked**: the app is blocked normally and may be allowed only as part of an approved request that explicitly includes soft blocked apps.

- [ONPC-CORE-APPS-006] Changing an app rule saves and applies it immediately; no separate Save action is required. App rules work whether screen-time control is enabled or disabled.
- [ONPC-CORE-APPS-007] Blocking prevents use of the selected app rather than merely hiding its launcher. For a supported native app, the same executable is blocked when started from the app grid, a desktop launcher, a file manager, or a command. For a supported Flatpak app, the selected Flatpak app is blocked through its app identity.
- [ONPC-CORE-APPS-008] A precise match covers the app's current executable. A pattern match may be used for a versioned AppImage filename in the same directory; matching new versions are blocked while nonmatching files in that directory remain usable.
- [ONPC-CORE-APPS-009] Application blocking covers the supported app target selected in the Parent App. It does not claim to control a separately copied or renamed executable, scripts run through a shared interpreter, unsupported shared launchers, web content, or remote devices.
- [ONPC-CORE-APPS-010] When an app updates between being displayed and being saved, the rule applies to its current executable. If an app disappears, its saved rule is retained so it is not silently forgotten.
- [ONPC-CORE-APPS-011] An approved “Allow soft blocked apps” request temporarily removes only soft blocks. Hard blocks remain active. Grant expiry locks the child but does not immediately close applications in the retained session. Before the child next uses a new or unlocked session, the broker re-reads the current grant. If it is still expired, the broker restores the complete hard-and-soft policy and stops the child's blocked applications. If it has been replaced by an active grant, that grant's selected app policy takes precedence. In particular, a replacement grant allowing soft apps leaves the hard-only policy and all running applications unchanged. Parent revocation and reapplying screen-time settings also restore the complete policy.

### Requesting and approving access

- [ONPC-CORE-REQUEST-001] A child with screen-time control enabled can select the remaining-time panel control to open the request form over their current session. The child account is fixed to the signed-in account and cannot be changed in this form.
- [ONPC-CORE-REQUEST-002] The same request form is available from the dedicated request-station account on the sign-in screen. It runs as a request-only session, lets the requester select a child, and provides no general desktop or parent-management access.
- [ONPC-CORE-REQUEST-003] If screen-time control is not enabled for the selected child, the form clearly says so and does not allow a request to be submitted.
- [ONPC-CORE-REQUEST-004] A request offers a selection of predefined durations, an option for the rest of the day, or a custom value from 0.1 through 1440 minutes. Invalid custom values are rejected before asking for approval.
- [ONPC-CORE-REQUEST-005] The requester selects one eligible parent and whether the grant should allow soft blocked apps. The approval prompt is restricted to that selected parent and identifies the child, requested duration, and soft-app choice.
- [ONPC-CORE-REQUEST-006] Parent credentials are entered only into the system authentication prompt. The child app and request station do not receive, store, or display the password.
- [ONPC-CORE-REQUEST-007] One successful authentication approves the complete request. It does not give the child or request station reusable administrator access or permission to make other account changes.
- [ONPC-CORE-REQUEST-008] A fixed-duration request adds the selected amount to whichever currently provides more usable time: the unused daily allowance or the unexpired one-time grant. A request therefore accumulates correctly and never replaces a later existing expiry with an earlier one.
- [ONPC-CORE-REQUEST-009] Approval applies the new time and the selected soft-app access together. Success is shown only after both are active and verified.
- [ONPC-CORE-REQUEST-010] When a request is approved without “Allow soft blocked apps,” all hard- and soft-blocked apps the child currently has open close immediately, on every desktop where that child is signed in. The extra time starts only after those apps have closed.
- [ONPC-CORE-REQUEST-011] When a request is approved with “Allow soft blocked apps,” no open apps are closed. Even an already-open hard-blocked app stays open, although hard-block rules still prevent new launches.
- [ONPC-CORE-REQUEST-012] Only the child whose request was approved is affected. Apps opened by anyone else stay open.
- [ONPC-CORE-REQUEST-013] A rejected password shows “Request denied” and leaves the choices available for another attempt. Cancelling the authentication prompt returns to the same form without treating cancellation as an error.
- [ONPC-CORE-REQUEST-014] Cancelling the child form closes only the overlay. Cancelling the dedicated request station returns to the sign-in screen. Escape has the same effect when no authentication prompt is active.
- [ONPC-CORE-REQUEST-015] After approval, the child overlay closes and the dedicated request station returns to the sign-in screen after a brief confirmation.
- [ONPC-CORE-REQUEST-016] The selected duration, custom value, approving parent, and soft-app choice are remembered per child and shared between the child and request-station forms. Sound mute is remembered separately for those two places.

### Revocation, persistence, and failures

- [ONPC-CORE-RECOVERY-001] A parent can revoke a child's active one-time grant after confirmation. All hard- and soft-blocked apps the selected child has open close immediately, on every desktop where that child is signed in, and the one-time grant is removed. The child's unused daily allowance is unchanged, and apps opened by anyone else stay open.
- [ONPC-CORE-RECOVERY-002] Parent settings and request-form choices survive application restarts, broker restarts, sign-out, and reboot.
- [ONPC-CORE-RECOVERY-003] After a broker or package restart, every enabled child still receives the current child-session component and the saved policy remains enforced.
- [ONPC-CORE-RECOVERY-004] Invalid, unauthorized, denied, cancelled, interrupted, or failed operations do not grant time, relax an app rule, or partially change screen-time or app policy. Remembered request-form choices may still reflect the requester's last selection.
- [ONPC-CORE-RECOVERY-005] If a multi-part change fails, the previous working state is restored. The UI reports that the action failed and does not present it as successful.
- [ONPC-CORE-RECOVERY-006] Closing an app cannot be undone. If the product cannot close every required app during approval, revocation, or expired-grant session preparation, it reports that the action failed. Apps already closed stay closed, all hard and soft app blocks stay in place, and other users remain unaffected. Approval and revocation also preserve the child's prior time state as specified for their transaction.
- [ONPC-CORE-RECOVERY-007] Only one approval, revocation, or session-entry reconciliation transaction runs at a time. Rapid repeat submissions are refused rather than counted twice; a denied or cancelled approval attempt does not consume the repeat-request interval.
- [ONPC-CORE-RECOVERY-008] Request screens show a simple actionable error without exposing system paths, service names, or other backend details. Failure of the authentication helper denies that request but does not permanently break the request station; a later request can be attempted.

## 2. Component specifications

### Parent App

- [ONPC-COMP-PARENT-001] Starts only for a current local administrator and does not open a management window when access is denied or the broker is unavailable.
- [ONPC-COMP-PARENT-002] Lists eligible children, selects one child at a time, and loads that child's screen-time status, app list, and saved settings. If no child exists, it says that no interactive non-administrator account was found.
- [ONPC-COMP-PARENT-003] Lets the parent enable or disable screen-time control, choose a daily allowance, inspect today's remaining time, and revoke active one-time access. The revocation confirmation warns that the selected child's running blocked apps will close.
- [ONPC-COMP-PARENT-004] Lets the parent search and filter the selected child's app list, assign one of the three access rules, and choose a precise or version-tolerant match where supported.
- [ONPC-COMP-PARENT-005] Saves each change automatically in interaction order. While data is loading or saving, conflicting controls are unavailable. A failed save restores the last confirmed values and reports the failure.
- [ONPC-COMP-PARENT-006] Never grants additional time; it manages policy and revokes grants only.

### Request station

- [ONPC-COMP-KIOSK-001] Opens only in the dedicated, restricted request-station session and always provides a way back to the sign-in screen.
- [ONPC-COMP-KIOSK-002] Lists eligible children and eligible approving parents, then loads the saved request choices for the selected child.
- [ONPC-COMP-KIOSK-003] Keeps the request unavailable until accounts and the selected child's settings have loaded. It explains when no child or no approving parent is available.
- [ONPC-COMP-KIOSK-004] Prevents duplicate submissions while a request or authentication prompt is in progress.
- [ONPC-COMP-KIOSK-005] Submits only the displayed child, parent, duration, and soft-app choice. It shows approval, denial, cancellation, and service failure as specified in the end-to-end behavior.
- [ONPC-COMP-KIOSK-006] Remains request-only after success or failure and cannot be used to edit daily allowances, app rules, user accounts, or system settings.

### Child app

- [ONPC-COMP-CHILD-001] Is packaged as an immutable system extension so every new Shell session can discover it, but is activated only for children whose screen-time control is enabled. In a running Shell, activation succeeds only when Shell reports the extension enabled and active; disabling succeeds only when it reports the extension disabled and inactive. Without a running Shell, the desired state is persisted for the next login.
- [ONPC-COMP-CHILD-002] Shows a panel control only in the child's unlocked desktop and only while usable time remains. It does not show on the sign-in screen or lock screen.
- [ONPC-COMP-CHILD-003] Uses the current daily-time estimate and the current verified one-time grant to display remaining time. A temporary read failure preserves the last known estimate rather than inventing a replacement.
- [ONPC-COMP-CHILD-004] Opens at most one request overlay at a time. The overlay uses the signed-in child automatically, offers only eligible parents, and cannot manage another account.
- [ONPC-COMP-CHILD-005] Refreshes remaining time when a grant changes and after the request overlay closes. On login and each transition from locked to unlocked it calls the child-owned broker session-preparation method. It does not decide grant validity, modify app policy, or terminate processes itself.
- [ONPC-COMP-CHILD-006] Locks the child's desktop at zero time through the supported desktop lock and repeats enforcement if necessary. It does not log the child out or terminate another user's session.
- [ONPC-COMP-CHILD-007] Has no independent settings screen, no parent-management capability, and no custom control inside the system lock screen.

### Broker

- [ONPC-COMP-BROKER-001] Is the authority behind all three apps: account discovery, per-child settings, remaining-time calculation, approvals, grants, app enforcement, and revocation.
- [ONPC-COMP-BROKER-002] Determines the caller's real account for every operation. It never trusts a front end to claim that it is a parent, child, or the request station.
- [ONPC-COMP-BROKER-003] Rechecks that children and approving parents are still eligible before making a protected change, including after authentication. A child request always targets the calling child and cannot name another child.
- [ONPC-COMP-BROKER-004] Allows only parents to manage screen time, app rules, or revocation; only the dedicated request station to request for a selected child; and only an enabled child to request for itself.
- [ONPC-COMP-BROKER-005] Keeps one validated, private settings record per child. Front ends cannot read or edit those records directly, and one child's record cannot be used for another account.
- [ONPC-COMP-BROKER-006] Calculates daily time from today's recorded use and combines it with current and requested grants according to the end-to-end rules. It rejects invalid or implausible values instead of granting access.
- [ONPC-COMP-BROKER-007] Authenticates exactly the selected parent for exactly the displayed request. If the requester disconnects or an account or setting changes while approval is in progress, it rejects the stale request without changing access.
- [ONPC-COMP-BROKER-008] Applies screen-time, grant, and app-policy changes as verified all-or-nothing operations. It restores the previous state if any part fails and reports a distinct failure if restoration itself cannot be verified.
- [ONPC-COMP-BROKER-009] Applies saved app blocks to the selected child across supported launch routes, without affecting other users. App-policy activation is complete before a related change or grant is reported as successful. At child session entry it derives the child from the caller and re-reads `ActiveExtension` under the shared grant transaction lock. An expired grant restores the canonical hard-and-soft filter before the broker terminates that child's blocked apps. Any current grant—including one renewed after an earlier expiry—makes session preparation a no-op, preserving the live policy and processes established by that grant's approval.
- [ONPC-COMP-BROKER-010] Before serving app operations at startup, makes execution protection match the current child app filters and reasserts activation of the packaged child component for each enabled child. A managed sign-in must not begin during startup before application enforcement is ready.
