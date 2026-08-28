# Design & Implementation Spec: GNOME Shell “Request More Time” Extension

## 1. Objective

Build a GNOME Shell extension for Ubuntu 26.04 / GNOME 50 that adds a **“Request More Time”** button to the existing GNOME parental-controls lock-screen UI.

The button must appear **only when the child’s screen-time limit has actually been exhausted**, i.e. in the same lock-screen state where GNOME’s built-in **“Ignore”** button appears.

The extension must:

1. Run in GNOME Shell's `unlock-dialog` session mode.
2. Detect the parental-controls time-limit-exhausted state reliably.
3. Add a **Request More Time** button to the existing parental-controls lock-screen UI.
4. Leave GNOME's native **Ignore** button untouched initially.
5. Open a custom Shell-native dialog when the new button is clicked.
6. Let the child select a requested duration.
7. Integrate with Malcontent's existing temporary-extension mechanism if possible.
8. Never bypass or weaken GNOME/Malcontent enforcement.
9. Never replace or intercept the Polkit authentication mechanism.
10. Cleanly remove all UI and signal handlers when the extension is disabled/destroyed.

The initial implementation should NOT modify/fork GNOME Shell or Malcontent.

---

# 2. Target environment

Primary target:

- Ubuntu 26.04
- GNOME Shell 50
- Wayland
- Malcontent 0.14.x

The implementation must target the actual Ubuntu 26.04 versions installed on the development machine.

Do NOT assume APIs based solely on online documentation.

Before implementing anything, inspect the locally installed/source-available GNOME Shell and Malcontent implementation.

---

# 3. Important architectural decision

Use a GNOME Shell extension.

Do NOT:

- modify GDM;
- create a GDM extension;
- patch GNOME Shell;
- fork Malcontent;
- create a separate fullscreen GTK application;
- replace Polkit;
- implement an independent screen-time enforcement daemon.

The intended architecture is:

```text
GNOME Shell
    |
    | child reaches time limit
    v
ParentalControlsShield
    |
    +-- Ignore                    <-- native GNOME behavior
    |
    +-- Request More Time         <-- this extension
             |
             v
      Custom Shell dialog
             |
             v
      Malcontent extension
      /authorization mechanism
```

---

# 4. Critical functional requirement

The extension MUST NOT display “Request More Time” merely because the screen is locked.

For example:

```text
Child manually locks screen
    -> NO Request More Time

Parent locks screen
    -> NO Request More Time

Normal unlock dialog
    -> NO Request More Time

Child still has screen time remaining
    -> NO Request More Time

Child has exhausted parental-control screen time
    -> YES Request More Time
```

The button must appear only in the same state as GNOME's parental-control **Ignore** button.

---

# 5. First task: inspect the real GNOME Shell implementation

Before writing implementation code, inspect the actual GNOME Shell 50 source on the development system.

Locate and inspect, at minimum:

```text
js/gdm/authPrompt.js
js/misc/timeLimitsManager.js
js/ui/unlockDialog.js
js/ui/screenShield.js
```

Also search the entire GNOME Shell source tree for:

```text
ParentalControlsShield
shouldLockSession
timeLimitsManager
Ignore
parental-controls
session-limits
setAuthBlocked
```

Determine exactly:

1. Where `ParentalControlsShield` is defined.
2. How the native Ignore button is created.
3. What container the Ignore button belongs to.
4. How `ParentalControlsShield` is inserted into `AuthPrompt`.
5. When it is destroyed.
6. How `Main.timeLimitsManager.shouldLockSession` is exposed.
7. Which GObject signals/properties indicate changes to `shouldLockSession`.
8. Whether the shield has an identifiable public or semi-public actor/container that an extension can safely augment.
9. Whether there is a cleaner extension integration point than directly manipulating `_parentalControlsShield`.

Do not guess property names or signal names.

Document the findings in a developer note before proceeding.

---

# 6. Time-limit detection

GNOME Shell 50 has:

```js
Main.timeLimitsManager
```

and the relevant state is expected to involve:

```js
Main.timeLimitsManager.shouldLockSession
```

Verify this against the actual installed GNOME Shell 50 source.

The expected condition is conceptually:

```js
const exhausted =
    Main.timeLimitsManager.shouldLockSession;
```

However, verify:

- exact property name;
- exact semantics;
- whether it is true for all parental-control restrictions or specifically screen-time exhaustion;
- whether it also becomes true for bedtime restrictions;
- exact change signal.

Do not use polling unless there is no reliable event/property notification mechanism.

Preferred implementation:

```text
TimeLimitsManager state change
        |
        v
update button visibility
```

rather than:

```text
setInterval(...)
```

---

# 7. Distinguish daily exhaustion from other restrictions

The desired feature is specifically:

> Child has exhausted the daily screen-time allowance.

Investigate whether:

```text
shouldLockSession
```

also represents:

- bedtime restrictions;
- other parental-control restrictions;
- manually locked sessions;
- other screen-time states.

If the existing Malcontent/GNOME APIs expose enough information to distinguish daily-limit exhaustion from bedtime, use that information.

If they do not, document the ambiguity and choose the safest behavior.

Do NOT assume that `shouldLockSession == true` automatically means "daily allowance exhausted" without checking the GNOME 50 source.

---

# 8. Extension metadata

Create:

```text
metadata.json
```

with GNOME Shell 50 support and:

```json
"session-modes": [
    "user",
    "unlock-dialog"
]
```

The extension must be able to run while the lock/unlock dialog is displayed.

Use a proper UUID, e.g.:

```text
request-more-time@example.com
```

unless the project already has an established UUID.

---

# 9. Initial UI strategy

Do NOT replace GNOME's native Ignore button.

Initially the UI should be:

```text
+--------------------------------------+
|                                      |
|       Screen time limit reached      |
|                                      |
|       [ Ignore ]                     |
|       [ Request More Time ]          |
|                                      |
+--------------------------------------+
```

The native Ignore button must continue to behave exactly as GNOME intended.

The extension owns only:

```text
Request More Time
```

This provides a safe fallback and makes debugging easier.

---

# 10. Adding the button

Preferred approach:

1. Locate the existing `ParentalControlsShield`.
2. Locate its existing action/button container.
3. Add the new button to the same UI hierarchy if possible.
4. Do not replace the existing actor.
5. Do not monkey-patch GNOME Shell methods unless absolutely necessary.
6. Keep references to all actors created by the extension.
7. Remove them during extension disable/destroy.

Because `ParentalControlsShield` may be an internal Shell implementation rather than a stable public extension API, isolate all GNOME-Shell-internal access in one small module.

For example:

```text
src/
    extension.js
    parentalControlsIntegration.js
    requestDialog.js
    malcontentClient.js
```

`parentalControlsIntegration.js` should contain all GNOME Shell implementation-specific code.

This makes future GNOME upgrades easier.

---

# 11. Button lifecycle

The button must be created only when:

```text
unlock-dialog is active
AND
parental-control time limit is exhausted
AND
the parental-controls shield exists
```

If any of these become false:

```text
remove/hide the button
```

Examples:

```text
Child clicks Request More Time
    -> dialog opens

Child cancels dialog
    -> button remains

Parent approves request
    -> button should disappear when the session becomes usable

Child unlocks normally
    -> button removed

Lock screen destroyed
    -> button destroyed

Extension disabled
    -> button destroyed
```

Do not leave stale Shell actors behind.

---

# 12. Custom dialog

Use GNOME Shell's native modal-dialog infrastructure.

Do NOT launch a separate GTK process/application.

Expected UI:

```text
+--------------------------------------+
|        Request More Time             |
|                                      |
|  How much additional time?           |
|                                      |
|  ( ) 15 minutes                      |
|  ( ) 30 minutes                      |
|  ( ) 1 hour                          |
|  ( ) Until end of day                |
|                                      |
|                    [Cancel] [Request]|
+--------------------------------------+
```

The exact visual design can follow GNOME HIG conventions.

Use Shell-native components such as:

```js
St
ModalDialog
Clutter
```

as appropriate.

The dialog must work correctly in `unlock-dialog`.

---

# 13. Duration choices

Initial choices:

```text
15 minutes
30 minutes
60 minutes
Until end of day
```

Represent them internally as durations, not strings.

Example:

```js
const durations = {
    FIFTEEN_MINUTES: 15 * 60,
    THIRTY_MINUTES: 30 * 60,
    ONE_HOUR: 60 * 60,
    END_OF_DAY: ...
};
```

Do not hard-code the "end of day" calculation incorrectly.

Use the local timezone and current date.

---

# 14. Malcontent integration research

Before implementing the request action, inspect the actual Malcontent 0.14 source/API.

Search for:

```text
request-extension
extension
malcontent-timer-extension-agent
malcontent-timerd
D-Bus
temporary
```

Inspect:

```text
malcontent-client
malcontent-timer-extension-agent
malcontent-timerd
libmalcontent
```

Determine:

1. Exact D-Bus interface.
2. Exact object path.
3. Exact method name.
4. Exact method parameters.
5. Exact duration semantics.
6. Whether arbitrary durations such as 15/30/60 minutes are supported.
7. Whether duration `0` means "until end of day".
8. How authorization is performed.
9. Whether the existing `malcontent-timer-extension-agent` can be reused.
10. Whether the request must originate from the child user's session.
11. Whether a request can safely originate from GNOME Shell.

Do not invent D-Bus interfaces.

Use introspection where possible:

```bash
busctl introspect ...
```

and/or:

```bash
gdbus introspect ...
```

and inspect installed source/header files.

---

# 15. Security model

The extension MUST NOT grant time directly.

Bad:

```text
child clicks Request
    -> extension grants 30 minutes
```

Correct:

```text
child clicks Request
    -> extension submits request
    -> privileged authorization occurs
    -> parent approves
    -> Malcontent grants extension
```

The extension must not:

- run as root;
- modify AccountsService database directly;
- modify Malcontent policy files directly;
- bypass Polkit;
- disable Malcontent;
- alter PAM configuration;
- manipulate system clocks;
- fake usage records.

---

# 16. Parent authorization

Investigate whether the existing:

```text
malcontent-timer-extension-agent
```

can be used.

If it can:

```text
Request More Time
       |
       v
Malcontent request-extension
       |
       v
Existing extension agent
       |
       v
Polkit
       |
       v
Parent authentication
       |
       v
Temporary extension
```

Prefer reusing this infrastructure.

Do not implement a second authorization system unless the existing API fundamentally cannot support the required behavior.

---

# 17. Important distinction: child UI vs parent authorization

The custom dialog is a **child-facing request UI**.

It is not itself authorization.

Therefore:

```text
Child:
    Request More Time
    -> selects 30 minutes
    -> clicks Request

Parent:
    receives appropriate authorization prompt
    -> authenticates
```

The child must never be able to approve their own request.

---

# 18. Error handling

Handle at least:

```text
Request rejected
Parent cancels
Authentication failure
Malcontent unavailable
D-Bus failure
Invalid duration
Session no longer locked
Time limit state disappeared
Extension disabled
```

The child should receive a simple failure message, for example:

```text
Your request could not be approved.
```

Do not expose internal D-Bus or Polkit errors to the child unless useful.

Log detailed errors to GNOME Shell's extension logging.

---

# 19. Lock-screen constraints

Because the extension runs in:

```text
unlock-dialog
```

follow GNOME Shell extension review/security requirements for that mode.

In particular:

- do not install unnecessary keyboard event handlers;
- if any keyboard event handlers are used, ensure they are disabled/disconnected in `unlock-dialog`;
- do not collect sensitive information;
- do not log passwords;
- do not interfere with the normal unlock flow.

The extension should use buttons and Shell UI controls rather than attempting to intercept authentication.

---

# 20. Parent identity / child identity

The extension must operate on the currently restricted child session.

Do not assume:

```text current Shell user == administrator
```

The relevant identity is the child whose session has been restricted.

Determine how GNOME/Malcontent identifies the current restricted session.

Prefer existing GNOME Shell/Malcontent session identity APIs.

Do not hard-code a username.

---

# 21. Testing strategy

Implement automated/unit tests where practical, plus manual integration tests.

## Test A — normal desktop

Expected:

```text
No Request More Time button.
```

## Test B — manually lock child session

Expected:

```text
No Request More Time button.
```

## Test C — child has time remaining

Expected:

```text
No Request More Time button.
```

## Test D — daily limit exhausted

Expected:

```text
GNOME parental-controls shield appears.
Ignore appears.
Request More Time appears.
```

## Test E — click Request More Time

Expected:

```text
Custom duration dialog appears.
```

## Test F — cancel

Expected:

```text
Dialog closes.
Child remains restricted.
```

## Test G — request 30 minutes

Expected:

```text
Parent authorization is requested.
```

## Test H — parent rejects

Expected:

```text
Child remains restricted.
```

## Test I — parent approves

Expected:

```text
Child can continue using session.
```

## Test J — extension disabled

Expected:

```text
No custom UI remains.
GNOME's native Ignore behavior remains intact.
```

## Test K — next day

Expected:

```text
Temporary extension does not permanently alter the daily policy.
Normal daily limit applies again.
```

---

# 22. Development phases

Implement in this exact order.

## Phase 1 — Source investigation

Do not modify UI.

Deliver:

```text
docs/gnome50-integration.md
docs/malcontent014-integration.md
```

Document:

- relevant GNOME Shell classes;
- relevant properties/signals;
- parental-controls shield lifecycle;
- exact button container;
- exact exhausted-time state;
- Malcontent D-Bus API;
- extension-agent behavior.

Stop if the APIs cannot be determined reliably.

---

## Phase 2 — Detection prototype

Implement:

```text
Main.timeLimitsManager
        +
unlock-dialog
        +
exhausted-time detection
```

Log state transitions.

Do not add UI yet.

Acceptance criterion:

The extension logs the exhausted-time state only when the native Ignore UI is expected.

---

## Phase 3 — Button

Add:

```text
Request More Time
```

without changing native Ignore.

Acceptance criterion:

The button appears exactly alongside Ignore when the parental-control limit is exhausted.

---

## Phase 4 — Dialog

Implement the Shell-native custom duration dialog.

Acceptance criterion:

The child can select:

- 15 min
- 30 min
- 60 min
- end of day

and cancel safely.

No actual time granting yet.

---

## Phase 5 — Malcontent request

Connect the Request button to the real Malcontent extension mechanism.

Acceptance criterion:

The request reaches the existing Malcontent authorization infrastructure.

---

## Phase 6 — End-to-end approval

Verify:

```text
Child
  -> Request More Time
  -> selects 30 minutes
  -> Request
  -> parent authorization
  -> parent approves
  -> 30 minutes granted
  -> child session becomes usable
```

Also test rejection.

---

# 23. Compatibility strategy

The first release targets:

```text
GNOME Shell 50 / Ubuntu 26.04
```

Do not add Ubuntu 24.04 compatibility initially.

The code should nevertheless isolate GNOME Shell internals so future compatibility can be added without rewriting the entire extension.

Example:

```text
parentalControlsIntegration.js
```

should be the only module that knows about:

```text
ParentalControlsShield
AuthPrompt
_private Shell actors
```

---

# 24. Logging

Use a consistent prefix:

```text
[request-more-time]
```

Example:

```text
[request-more-time] extension enabled
[request-more-time] entered unlock-dialog
[request-more-time] parental control limit exhausted
[request-more-time] showing request button
[request-more-time] request dialog opened
[request-more-time] requesting 1800 seconds
[request-more-time] request submitted
[request-more-time] request approved
[request-more-time] request rejected
```

Never log:

- passwords;
- authentication secrets;
- sensitive Polkit details;
- unnecessary personal information.

---

# 25. Code quality requirements

The implementation must:

- use modern GNOME Shell 50 JavaScript imports;
- avoid deprecated GNOME Shell APIs where alternatives exist;
- avoid monkey-patching unless absolutely necessary;
- keep GNOME-internal integration isolated;
- clean up all signals;
- clean up all actors;
- clean up dialogs;
- avoid timers/polling unless required;
- avoid root privileges;
- avoid external dependencies;
- avoid modifying system files.

Follow GNOME Shell extension conventions.

---

# 26. Do not make these assumptions

The coding agent MUST NOT assume any of the following without source verification:

```text
ParentalControlsShield is public API.
AuthPrompt._parentalControlsShield is stable API.
shouldLockSession means only daily-limit exhaustion.
request-extension accepts arbitrary durations.
duration=0 means end-of-day in every context.
malcontent-timer-extension-agent automatically handles requests from any client.
the child username can be obtained from the Shell global.
the native Ignore button's actor hierarchy will remain unchanged.
```

Verify each against GNOME Shell 50 / Malcontent 0.14 source or D-Bus introspection.

---

# 27. Definition of done

The implementation is complete when all of the following are true:

### UI

- [ ] Extension loads on GNOME Shell 50.
- [ ] Extension runs in `unlock-dialog`.
- [ ] Request More Time is invisible during normal use.
- [ ] Request More Time is invisible during ordinary manual lock.
- [ ] Request More Time appears when the native parental-control Ignore button appears.
- [ ] Native Ignore button remains unchanged.
- [ ] Custom duration dialog works on the lock screen.

### Backend

- [ ] Existing Malcontent extension mechanism is used where possible.
- [ ] No independent time-enforcement system is implemented.
- [ ] Parent authorization is required.
- [ ] Child cannot authorize their own request.
- [ ] Exact requested duration is passed correctly.
- [ ] Rejection works.
- [ ] Approval works.
- [ ] Temporary extension does not permanently modify the daily policy.

### Reliability

- [ ] No polling unless unavoidable.
- [ ] All signal handlers are disconnected.
- [ ] All Shell actors are removed on disable.
- [ ] Dialogs are destroyed correctly.
- [ ] No stale UI remains after unlocking.
- [ ] No errors during extension disable/re-enable.

### Security

- [ ] No root daemon.
- [ ] No direct policy-file modification.
- [ ] No AccountsService database manipulation.
- [ ] No Polkit bypass.
- [ ] No authentication interception.
- [ ] No password handling.

---

# 28. Final implementation principle

The extension should be a **thin UI layer** over GNOME/Malcontent:

```text
                GNOME Shell
                    |
             TimeLimitsManager
                    |
             limit exhausted?
                    |
                   YES
                    |
                    v
          ParentalControlsShield
                    |
          +---------+---------+
          |                   |
       Ignore        Request More Time
          |                   |
      GNOME native        Custom dialog
          |                   |
       Polkit              Malcontent
          |                   |
       End-of-day       Requested duration
       override              |
                              v
                         Parent auth
                              |
                              v
                       Temporary access
```

The extension should **not become a replacement parental-control system**.

Its job is simply to provide the missing child-facing UX while delegating enforcement and authorization to the existing GNOME/Malcontent infrastructure.