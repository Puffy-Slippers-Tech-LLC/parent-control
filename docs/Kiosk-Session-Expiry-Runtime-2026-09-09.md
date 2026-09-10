# Kiosk expiry: automation VM runtime continuation

Continuation of the [original fix handoff](Kiosk-Session-Expiry-Fix-Handoff-2026-09-09.md)
on the main development computer. The user released the automation VM for these
checks. The installed-app machine described in that handoff is a different
computer. No product package was installed on the development host, and unrelated
staged and unstaged work was preserved.

**Installed runtime checks completed:** the latest package passed fresh-install
and old-to-new update runs, including all session checks listed below. Final
local validation passed 5,900 unit tests and 25 component tests. The VM is
restored to its accepted baseline and powered off. The request checks use real
broker/Polkit APIs and the foreground check uses a local VT; this is not a full
GUI customer-journey qualification. Earlier failed attempts remain intact.

## Inputs and scope

New artifacts were built here, rather than reusing the other computer's `/tmp`
paths. Both `/tmp/onpc-test-artifacts-y3grarvy` and
`/tmp/onpc-test-artifacts-d8ramxb3` contain the same package bytes:

- Package SHA-256: `12ad6400a7d120281f0473bc4334c067c0244856ce34917bc71bd055e72ed8ff`.
- Latest artifact source digest: `337d1fe1dad0f92315da84f164cf1322574266c3e5e83ca6c8ce1d03d09e7cc8`.
- Base revision: `944da18980cab1181c287ba9d59e88276cbea654`; uncommitted source is included.
- Finalized VM baseline provenance: `cffe72b4c77004a010d2b0341b415853c0afce838efe4762bb84a52665ca0eb5`.

The controller separately freezes and hashes each attempt's exact selected guest
tests/helpers. Test-tooling changes after package build therefore have their own
`selected_inputs_sha256`; they do not silently change the installed package.
The package remains version 1.0. Each attempt starts from the product-free baseline.

## Attempts

### Fresh installation and reboot observation

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-y3grarvy --area package`.
Evidence: `/tmp/onpc-system-4zo4j97d/evidence`.
Selected input digest: `a83d7e2b1d456469e08c3ff46f054a93d0044ede8c65732c5d43630f174dfab6`.

Fresh installation, installed file checks, PAM account ordering, broker activation
and first-install reboot notification passed. The old transport then failed with
`transport:reboot-not-observed`: the reboot closed its original SSH connection,
but another connection briefly read the old boot before sshd stopped. The next
collection connection was reset. The failed run is retained; cleanup passed and
restored the baseline, original domain configuration and powered-off state.

[Transport.reboot](../tests/integration/vm_transport.py) now reuses the existing
bounded boot-change observer. It waits through a valid old boot and SSH transport
resets, while refusing malformed output, guest guard failures, lost ownership,
command failure and deadline exhaustion. Focused regressions include the observed
old-boot/connection-reset/new-boot sequence.

### Installed PAM scopes and offline recovery

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-d8ramxb3 --area enforcement --test test_kiosk_expiry_installed_runtime`.
Evidence: `/tmp/onpc-system-5t4wbmqf/evidence`.
Selected input digest: `1010bd5f30c75b24b60b7311d5f2e2ed49a6551f53a3ebdd090f5bfb4ab81c3f`.

All four package/install/reboot checks passed; actual changed-boot observation
took 14.034 seconds. The focused check established:

| Observation | Result |
| --- | --- |
| Offline broker startup with global extensions disabled | Broker activated, switch restored, individual enabled/disabled selections preserved |
| Installed `gdm-password` PAM account phase | Accepted with 0.779 seconds remaining |
| Its real pam_systemd scope | `RuntimeMaxUSec=infinity`; still active past the original deadline |
| Installed `gdm-autologin` PAM account phase | Accepted with 0.800 seconds remaining |
| Its real pam_systemd scope | `RuntimeMaxUSec=infinity`; still active past the original deadline |
| Installed `login` PAM scope | Finite `RuntimeMaxUSec=3s` |

These PAM probes run outside the SSH scope in a test-started transient service.
They explicitly use an unspecified session type, excluding the broker's
graphical-only fallback. They invoke the installed stack and real pam_systemd,
but do not themselves start a GDM desktop.

The attempt failed at the `login` termination witness. The probe moved out of
its launcher service into the login scope; the launcher reported successful
deactivation when that scope ended. Its exit status is not the scope's timer
result. The fixture now requires the actual created scope's journal event,
`Scope reached runtime time limit. Stopping.` SSH remained untested in this
failed attempt. Collection and cleanup both passed. The failed result is not
relabelled as a passing run.

### Actual GDM admission at the one-second boundary

Two `--area session` attempts used `/tmp/onpc-test-artifacts-d8ramxb3`:

- `/tmp/onpc-system-rpupqwtk/evidence`, selected inputs
  `59d5ad115da2ae87b1d1c32e61417c936663c0514eb6541bd134edae368db068`:
  all package/reboot checks and all four PAM scope checks passed. The graphical
  observer raced the seed file because SSH was ready before GDM; no graphical
  result was established. The fixture now publishes atomically, waits under a
  deadline, and prevents a failed or completed seed from granting time again.
- `/tmp/onpc-system-hv8hu189/evidence`, selected inputs
  `287b4f32fe8c65eae53667960438470a38595490f4496e82f48632e97efb7e38`:
  package checks, offline recovery, both GDM infinite scopes, and both finite
  `login`/`sshd` scope terminations passed. A real GDM autologin admitted the
  child with **0.927 seconds** remaining and created a Wayland scope with
  `RuntimeMaxUSec=infinity`. The native before-session journal witness was
  present and the broker invocation had not changed since before admission.
  GNOME registered with GDM and the extension made broker calls. The observer
  then failed at `expiry:gnome-shell-unavailable`; locking and live recovery
  were not yet established. GNOME also logged a stylesheet error, retained in
  `session-journal.txt` for investigation.

Both attempts collected evidence and restored the accepted baseline, original
domain configuration and powered-off state successfully.

The second attempt exposed another product defect: `_shell_is_available`
checked the on-demand `org.gnome.Shell.Extensions` service, which need not have
started even while Shell runs the extension. The corrected probe checks
`org.gnome.Shell`. GNOME's
[extension proxy implementation](https://github.com/GNOME/gnome-shell/blob/50.1/js/dbusServices/extensions/extensionsService.js)
confirms that the separate service proxies to that Shell owner. Activation still
uses the supported CLI and requires actual configured/active readback; settings
alone cannot establish live recovery.

### Same-version update, expiry lock, and live recovery

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-cxnd_a7d --previous-artifacts /tmp/onpc-test-artifacts-sf_4_o28 --area session`.
Evidence: `/tmp/onpc-system-6zmcnp_2/evidence`.
Selected inputs: `f75ae22eec742ec1375e2efbcd90e109f5da335d7c2c4bda7af41022cb793cac`.

- Fixed package: `6737f84806918c29e25b560f2d4cb6c1458ff0ec7552aea463df5dd4a2f58188`.
- Source: `44742bfbde73a32ad051a68f021171abf5d55730a626504208d209f36ca4225a`,
  601 files based on `d89634de95b1f41b55a6970059928c4e54b6cf6a`.
- Prior package: `81f4790120273529ed65a2371728daf490540450e5bd647c66c0aa5d71ca743b`;
  its old external PAM helper was present before the update.

The old payload was verified and booted before APT installed the different new
bytes using `--reinstall`. Its product reboot marker was absent before the
update; the update requested a new reboot. All four installed/reboot assertions
passed after the update, including installed payload verification and PAM layout.

The PAM/offline prerequisites passed again. The real GDM login had 0.922 seconds
remaining and an infinite scope before any later broker restart. **Expiry locked
and retained that same desktop. Live broker recovery restored the global switch,
preserved selections, and verified the extension configured and active.**
GNOME's stylesheet error recurred, but did not prevent these observed behaviors.

The run then failed at the zero-time PAM assertion. The observer incorrectly
expected PAM_ACCT_EXPIRED for both PAM phases; upstream
[pam_malcontent](https://gitlab.freedesktop.org/pwithnall/malcontent/-/blob/0.14.0/pam/pam_malcontent.c)
returns PAM_AUTH_ERR for exhausted account time. The observer now records both
numeric statuses before checking the distinct authentication/account contracts.
Later request and injected-failure cases were not reached in this attempt.
Collection and cleanup passed, with baseline restoration taking 107.796 seconds.

### Offline failure injection and bounded PAM observer

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-cxnd_a7d --area session`.
Attempt directory: `/tmp/onpc-system-iuoq9sux`.
Selected inputs: `c197dc34d375f31aaaf9b313e71099e9fe916345af7fb99aa351d2c6aec6ae40`.

All package prerequisites passed. The retained
`graphical-expiry-prerequisites.json` establishes real offline dconf rollback
after injected write-response, readback, and activation failures. With verified
extension metadata temporarily withheld, actual broker startup failed, a child
request failed, the grant stayed unchanged, and the broker bus name remained
unowned. The exact metadata inode was restored and startup recovered. All four
PAM scope checks passed again.

The graphical phase hit its 900-second outer deadline. Broker logs show live
recovery verified configured/active, followed by the initial grant revocation
in the PAM admission block; the observer never reached that block's final
revocation or either approval request. Broker reconciliation continued normally.
No completed session JUnit survived, so later assertions are not treated as
passing. Collection and cleanup succeeded; baseline restoration took 84.310
seconds and the original domain configuration and powered-off state were restored.

The observer had performed multiple native PAM transactions inside one
long-lived Python process without a per-call timeout. Each transaction now runs
in a separate identity-recorded process under a 30-second command deadline,
with the secret only on stdin. Completed runtime assertions are also published
atomically in `session-observations.json`, preserving evidence if a later native
dependency stalls. This changes the test observer, not the installed PAM stack.

### Intermittent expiry-lock failure

Attempt: `/tmp/onpc-system-h8km6rk5/evidence`, using the same `cxnd_a7d` package.
Selected inputs: `d1f6cc8b9852dde004cc9a32d34298f5cdba91c9d0a5ff09117a9369372fba47`.

All four package prerequisites, offline recovery/failure injections, and all
four PAM scope checks passed. GDM admitted the child with 0.909 seconds remaining
and the correct infinite scope. The extension was configured/active and logged
zero remaining time, but logind never reported the desktop locked during the
90-second observation. No extension lock-request completion or error was logged.
The run failed with `expiry:desktop-not-locked` before reaching live recovery or
the newly bounded PAM probes. GNOME's stylesheet error recurred. This is an
unresolved intermittent runtime failure, not a passing lock assertion.
Collection and cleanup passed; baseline restoration took 73.345 seconds.

The next diagnostic package is `/tmp/onpc-test-artifacts-ex0zamjo`:

- Package: `d17bc256b5dd762d99efece60df24057a019305d15f88e697af7d7361527f62d`.
- Source: `7893136dfe2963b248a122c689683946559d105e382f1265ac7ed74e27cb0685`,
  603 files based on `d89634de95b1f41b55a6970059928c4e54b6cf6a`.

It adds deduplicated, PII-free expiry-state and lock-request diagnostics without
changing lock decisions. The guest observer records public ScreenSaver activity,
logind locking, password mode, and screen-lock settings. The owning controller
also captures the screen after a failed session test, preserving the original
failure if capture fails. These observations distinguish an unrequested lock
from a partial GNOME lock transition.

### Complete fresh-install runtime pass

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-ex0zamjo --area session`.
Evidence: `/tmp/onpc-system-odiirsrk/evidence`.
Selected inputs: `70a4ff00bb5bba2d6796c5e0634dc56a1cfe87de75de2562d782e3669b2c2435`.

All five registered executions passed: four installed/reboot prerequisites and
the complete session diagnostic. The completed observations establish:

| Handoff runtime check | Observed result |
| --- | --- |
| Real GDM admission near expiry | 0.905 seconds remaining; Wayland session; native before-session witness; unchanged broker invocation |
| Created GDM scope | `RuntimeMaxUSec=infinity`, retained after expiry |
| Expiry lock | Same session; logind locked and ScreenSaver active; lock enabled; lockdown false; normal password mode |
| Zero-time unlock authentication / fresh-login account check | PAM status 13 / 7; both became 0 with a real positive grant |
| Terminal and SSH timers | `3s` scopes reached their runtime limit and stopped |
| Offline and live broker recovery | Global switch restored, exact extension selections preserved, configured/active verified for the live Shell |
| Write-response, readback, activation failures | Actual settings and runtime rollback verified, in both offline and live modes |
| Actual unavailable enforcement | Broker startup and child request refused; no grant change or owned broker bus name; exact metadata restored and startup recovered |
| Child and kiosk request paths | Real public API calls with selected-parent Polkit authentication approved and read back |
| Extending an active grant | Same infinite session scope remained active past the earlier approved deadline |
| Another foreground account | Real local `login` PAM session on seat0/tty7 stayed active and unlocked across child expiry; its account state was unchanged |

All product, infrastructure, collection and cleanup outcomes passed. Cleanup
took 107.537 seconds and restored the baseline, original domain configuration and
powered-off state. The retained `session-screen.png` is a valid capture but shows
only "Display output is not active"; it is not visual proof of a lock screen.
The capture helper now sends only a fixed Shift modifier before capture and
rechecks ownership before and after waking/reading. Its ownership-loss and
original-failure preservation regressions pass.

The passing child log shows GNOME entering lock mode before the first completed
time estimate, so the product did not need to send its own Lock call. Upstream
[ScreenShield](https://github.com/GNOME/gnome-shell/blob/50.1/js/ui/screenShield.js)
acquires its logind proxy asynchronously and sends `SetLockedHint` only when that
proxy is present at the lock transition; it does not replay the hint when the
proxy arrives. This is a plausible explanation for the earlier missing hint,
not proof of what happened in that failed attempt. That attempt lacked the
ScreenSaver/state witnesses and remains recorded as an unresolved observation.
The recurrent GNOME stylesheet error also occurred during this passing run.

Full local `make check`: 5,890 unit and 25 component tests passed. Subsequent
capture-only changes passed 143 focused observer and cleanup tests. No product
package was installed on the development host.

### Update pass at installation; reproduced stale logind hint

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-ex0zamjo --previous-artifacts /tmp/onpc-test-artifacts-sf_4_o28 --area session`.
Evidence: `/tmp/onpc-system-jyrxuhc4/evidence`.
Selected inputs: `70a4ff00bb5bba2d6796c5e0634dc56a1cfe87de75de2562d782e3669b2c2435`.

The old package was installed, verified and rebooted. Updating to the latest
bytes requested the required new reboot; all four installed/reboot assertions
passed. Offline checks and all PAM scope checks passed. The actual GDM admission
had 0.912 seconds left and an infinite scope with the before-session witness.

The observer again failed because `LockedHint` stayed false. This time the
additional evidence distinguishes the failure:

- Native ScreenSaver `GetActive` returned true.
- Normal password mode was 0, screen locking was enabled, and lockdown was false.
- The extension reported `loaded=true limitEnabled=true locked=true greeter=false`.
- The captured `session-screen.png`, inspected after a fixed Shift wake,
  displays GNOME's lock screen. It is not an unlocked desktop.

This reproduces the suspected missed logind startup notification, rather than
an absent native lock. The preceding upstream source review explains why a
late logind proxy does not receive the initial hint. The older attempt lacked
these additional witnesses and is not retrospectively relabelled as passing.
Neither failed JUnit result is changed. Collection and cleanup passed, with
baseline restoration taking 103.950 seconds.

The observer now requires native ScreenSaver activity with normal password mode
and enabled, non-disabled screen locking, then separately requires the real
installed PAM authentication/account denials and the same retained session.
It preserves `LockedHint` as a diagnostic instead of treating it as an
authoritative negative. The corrected observer rejects an inactive ScreenSaver
even with a true logind hint, passwordless mode, disabled locking, malformed
responses and replaced sessions. Its focused observer/guard suite passed 141
tests. The installed product's locking decisions are unchanged.

### Complete update runtime pass

Command: `tools/run-tests system --artifacts /tmp/onpc-test-artifacts-ex0zamjo --previous-artifacts /tmp/onpc-test-artifacts-sf_4_o28 --area session`.
Evidence: `/tmp/onpc-system-41bhr66h/evidence`.
Selected inputs: `ea529e60ac7cf59ec69121e65c370bcfbb17731f66101842f3db3cb41960a577`.

All five registered executions passed, with no skipped cases. The selected
package and prior-package digests are unchanged from the preceding update
attempt. `update-activation.json` verifies that the old payload was booted,
the product reboot marker was absent before the same-version reinstall, and
the new payload requested the required reboot.

The real GDM login had **0.902 seconds** remaining and created an infinite scope
before any later broker restart. Native ScreenSaver activity and logind's hint
both confirmed locking in this run. The full fresh-install result matrix above
passed again: zero-time PAM denials and positive-time acceptance, live/offline
recovery and all injected rollbacks, actual startup refusal without enforcement,
both authenticated request APIs, retained scope past an extended grant's earlier
deadline, and the unaffected other user's foreground local VT.

`guest-results/session-screen.png` and the collected evidence copy show the
retained GNOME lock screen after the final expiry; the image was exported and
visually inspected. No credentials were typed or captured. GNOME's previously
recorded stylesheet warning recurred without preventing these assertions.

The final aggregate is `all-checks-passed`: product, infrastructure, collection
and cleanup all passed. Cleanup took 106.528 seconds and restored the accepted
baseline and original domain configuration. `tools/test-vm status` subsequently
reported state 5 (shut off), ID -1. No maintenance lease was left active.

Final `make check` passed **5,900 unit tests and 25 component tests**, including
the corrected observer and capture/ownership regressions. All maintained links
in the touched handoff/design/test documents and `git diff --check` passed.
No commit, reset, staging operation or product installation on the development
host was performed by this continuation.

The deployable package is
`/tmp/onpc-test-artifacts-ex0zamjo/package/oh-no-parent-control_1.0_amd64.deb`.
Its verified package SHA-256 is
`d17bc256b5dd762d99efece60df24057a019305d15f88e697af7d7361527f62d`.
The separately installed application on the original handoff computer remains
unchanged; installing the PAM fix there still requires its reboot boundary.

## Runtime fixture and coverage limits

The new registered `session` area uses the same controller, accepted baseline,
exclusive lease, immutable selected inputs, installed prerequisites and cleanup.
It repeats the installed PAM/offline checks, prepares a one-shot fixture, and
performs another real reboot. A guest-only `pam_exec` account hook seeds one
second of grant immediately before the unchanged stock account checks. It does
not override their status or create a synthetic desktop. The broker is started
before that hook returns, and its invocation identity must remain unchanged
through the initial scope observation, excluding a later startup cap repair.

The observer requires a real local graphical `gdm-autologin` user session,
the native module's before-session journal witness, an infinite scope, a live
configured/active extension, and the same retained session locked after expiry.
It then disables the global switch, waits for actual deactivation, and tests
broker recovery against live GNOME state and preserved settings lists.

This fixture uses [GNOME's documented automatic login configuration](https://help.gnome.org/system-admin-guide/login-automatic.html)
through AccountsService. It is an installed runtime diagnostic, not a password
entry or full customer-journey assertion. The handoff's installed-runtime checks
are complete with the fresh-install and update passes above. GUI click-through,
password entry through GDM, and a graphical Switch User journey remain outside
this diagnostic's coverage; they are not claimed by its API, PAM, or local-VT
results.
