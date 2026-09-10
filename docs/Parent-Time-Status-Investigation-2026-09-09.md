# Parent remaining-time authentication failure — 2026-09-09

Scope: fix the reported Parent App error in the copied client checkout. The
user reserved the testing VM for another session; no VM operation is authorized
for this investigation. Unrelated working-tree changes are preserved.

## Cause and correction

The parent log at `/var/log/oh-no-parent-control/parent/2026-09-09.log` records
successful time reads through 16:06:00 Pacific, repeated failures from 16:06:09
through 16:08:42, and recovery at 16:09:09. Each refresh exhausts its three
retries and opens the reported error dialog. The user supplied the underlying
`org.freedesktop.Accounts.Error.PermissionDenied: Authentication is required`
error; the old log records only its exception type.

The old client reads `ActiveExtension` directly from another account's
AccountsService object. The installed public interface annotates that read with
`com.endlessm.ParentalControls.SessionLimits.ReadAny`; the installed Polkit action
requires `auth_admin_keep` for active, inactive, and other callers. Administrator
role alone therefore does not authorize this direct read. Retained authorization
can explain intermittent success, but its lifetime was not recorded in the app
logs and is not established by this investigation.

[BrokerClient.get_time_status](../parent/oh_no_parent_control_parent/client.py)
now calls the existing `GetTimeStatus(uu) -> (uuuu)` broker method for all four
status values. The broker authorizes the live caller and target, reads the
grant, and invokes its usage helper under the selected child's identity. The
front end no longer requires direct AccountsService authorization or duplicates
usage arithmetic. Backend failures still reach the existing bounded retry and
unavailable UI; a failed read never becomes zero time. Client failure logs name
the broker stage and exception type without user identities or exception text.

The currently installed broker source already implements this method and usage
identity boundary. The parent client update activates on its next launch after
installation (`none` package activation); no API, Polkit, preference migration,
or reboot is required by this fix. The installed app has not been replaced.

## Verification

- Client regressions cover the reported denied direct-read condition, status
  mapping, default zero additional time, fresh expiry/renewal and child selection,
  and error propagation without sensitive log text.
- The broker regression confirms a parent's administrator/local role is
  revalidated before each usage or grant read. Existing broker property tests
  cover daily clipping, overlap merging, and grant arithmetic.
- The copied checkout is a `virtiofs` mount with `noexec`; direct execution of
  `tools/run-unit-tests` and `tools/read-only` returns permission denied even
  outside the sandbox. Verification uses the already-authorized plain
  `make check-unit` target, whose recipe invokes pytest directly.
- `make check-unit`: **5860 passed, 9 failed** in 154.06 seconds. All three
  parent-client cases, the new broker role check, and the existing broker
  arithmetic/property tests passed. The nine failures are the existing direct
  launcher cases on this `noexec` checkout: two slice-help cases, one document
  reader case, four E2E Make/launcher cases, the guest guard, and guest
  preparation. They match the previously recorded
  [checkout execution limitation](Kiosk-Feedback-Investigation-2026-09-09.md#validation).
- A read-only call to the installed broker as the signed-in administrator,
  using `busctl --system --timeout=35 --allow-interactive-authorization=no`
  with `GetTimeStatus uu <selected-child-uid> 0`, returned `uuuu 0 0 0 0`.
  The direct AccountsService read also succeeded at that later point; the
  intermittent historical denial was not reproduced or induced by clearing
  authorization. No account, grant, service, or installed file was changed.
- `git diff --check` passed. The required `tools/read-only links` invocation
  was blocked by the same `noexec` mount; automated Markdown link validation
  is not claimed. No VM or installed UI verification is claimed.

The fix remains a source change for packaging and installation, followed by
reopening the Parent App. Installed UI acceptance should verify periodic
remaining-time refresh with no retained AccountsService authorization when
the operator makes the testing VM available.
