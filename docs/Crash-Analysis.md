• ## What happened

  The kiosk session itself did not crash on Saturday, September 19.
  Instead, Ubuntu displayed an unprocessed crash report left by an
  earlier GNOME Kiosk crash on September 11.

  The underlying product-integration problem is that Kiosk=true
  suppresses XDG autostart .desktop files, but it does not suppress
  services globally enabled for graphical-session.target. Ubuntu’s
  crash reporter is one of those services, so it can create an
  unrelated window inside our supposedly request-only session.

  ### 1. How the intended kiosk session starts

  The GNOME session descriptor declares a kiosk session:

  - data/gnome-session/sessions/oh-no-parent-control.session:1 sets
    Kiosk=true.

  - This prevents ordinary XDG autostart desktop entries from
    starting.

  - The design therefore expects the session’s application set to
    come from systemd.

  The product session target then explicitly requests three main
  components in data/systemd/user/gnome-session@oh-no-parent-
  control.target.d/session.conf:1:

  - org.gnome.Kiosk.target: the GNOME Kiosk/Mutter compositor.
  - oh-no-parent-control-app.service: the Python request station.
  - oh-no-parent-control-polkit-agent.service: the authentication
    agent.

  That matches the documented request-only architecture.

  ### 2. The overlooked systemd dependency

  The product-specific target also inherits GNOME’s ordinary session
  hierarchy:

  gnome-session@oh-no-parent-control.target
  └── requires gnome-session.target
      └── binds to graphical-session.target
          └── wants update-notifier-crash.path

  Ubuntu installs this system-wide symlink:

  /usr/lib/systemd/user/graphical-session.target.wants/
      update-notifier-crash.path

  Consequently, every graphical session—including the dedicated kiosk
  session—starts Ubuntu’s crash-report watcher.

  The relevant Ubuntu unit is /usr/lib/systemd/user/update-notifier-
  crash.path:1:

  [Unit]
  PartOf=graphical-session.target

  [Path]
  PathChanged=/var/crash/

  When /var/crash changes, it activates /usr/lib/systemd/user/update-
  notifier-crash.service:1, which runs:

  /usr/lib/update-notifier/update-notifier-crash

  That script searches for unprocessed crash reports accessible to
  the current user and launches apport-gtk. It has no knowledge that
  this is a restricted request-station session.

  Therefore:

  - Kiosk=true successfully blocks .desktop autostarts.
  - It does not block globally enabled systemd user units.
  - Ubuntu’s Apport GTK dialog becomes an additional window in the
    kiosk session.

  - The existing “complete application set” statement in docs/
    SystemDesign/Frontends.md:39 is broader than the installed
    behavior actually guarantees.

  ### 3. Why the old report was considered new

  Apport considers a report unseen when its access time is not later
  than its modification time. The logic is in /usr/lib/python3/dist-
  packages/apport/fileutils.py:196.

  The report was:

  /var/crash/_usr_bin_gnome-kiosk.1002.crash

  Its filesystem birth time was September 11 at 7:55:32 PM. The
  photographs independently show:

  - ExecutablePath: /usr/bin/gnome-kiosk
  - gnome-kiosk crashed with SIGSEGV
  - Signal: 11
  - SourcePackage: gnome-kiosk
  - Date: Fri Sep 11 19:55:31 2026

  It remained unprocessed until the Saturday kiosk session. When the
  path watcher fired, apport-checkreports found it and apport-gtk
  displayed the generic “Ubuntu 26.04 has experienced an internal
  error” dialog.

  This can happen with any qualifying crash report accessible to the
  kiosk account, not just a GNOME Kiosk report.

  ### 4. Saturday’s exact sequence

  On Saturday, September 19:

  1. At 2:03:23 PM, the computer resumed from suspend.
  2. At 2:03:25–2:03:26, the dedicated kiosk session started.
  3. GNOME Kiosk started as PID 6257.
  4. The request station and authentication agent started normally.
  5. update-notifier-crash.path also started as part of the inherited
     graphical session.

  6. At 2:04:35, update-notifier-crash.service started and identified
     gnome-kiosk.

  7. The stale Apport dialog appeared. The service remained active
     until 2:06:14, consistent with the dialog remaining open.

  8. Authentication completed at approximately 2:06:16.
  9. The request station intentionally returned to login at 2:06:17.
  10. GNOME Kiosk PID 6257 then stopped normally. There was no
     Saturday compositor crash.

  The product app and broker logged a successful request, not an
  exception.

  ### 5. Why a successful app exit shuts down the session

  When a kiosk request succeeds—or the user cancels—the request
  station calls Application.quit() in kiosk/
  oh_no_parent_control_kiosk/main.py:1235.

  The app’s systemd unit contains:

  OnFailure=gnome-session-shutdown.target
  OnSuccess=gnome-session-shutdown.target

  See data/systemd/user/oh-no-parent-control-app.service:1.

  The sequence is intentional:

  1. The GTK application exits normally.
  2. systemd records the service result as successful.
  3. OnSuccess= starts gnome-session-shutdown.target.
  4. That target conflicts with the active GNOME and graphical-
     session targets.

  5. GNOME Kiosk, the authentication agent, portals, and other
     session services stop.

  6. GDM returns to the sign-in screen.

  OnFailure= provides the same cleanup if the request station
  crashes, avoiding a stranded compositor with no usable request UI.

  ### 6. Relationship to the original September 11 crash

  The September 11 report was product-adjacent but not a crash in our
  Python application.

  The earlier sequence was:

  1. The request was approved at 7:55:30 PM.
  2. The app requested return to login at 7:55:31.
  3. oh-no-parent-control-app.service exited successfully.
  4. OnSuccess= initiated normal session shutdown.
  5. GNOME Kiosk began stopping.
  6. GNOME Kiosk emitted:

     clutter_seat_is_unfocus_inhibited:
     assertion 'CLUTTER_IS_SEAT (seat)' failed

  7. It immediately segfaulted inside libmutter-18.so.
  8. Its stop operation then timed out, and systemd killed the
     remaining process.

  Thus:

  - Our normal logout initiated the shutdown path.
  - The actual defect occurred inside GNOME Kiosk/Mutter.
  - The same shutdown completed normally on September 19 and during
    other observed kiosk sessions, so the compositor fault is
    intermittent.

  - Current installed versions are gnome-kiosk 50.0-1 and libmutter-
    18-0 50.1-0ubuntu2.2.

  ## Why this matters

  There are two separate issues:

  1. Restricted-session isolation: Ubuntu’s crash-report UI was
     allowed into a request-only session. This is a product
     integration defect and can obscure the request form, steal
     focus, interrupt authentication, confuse the user, and expose an
     unintended system-information surface.

  2. GNOME Kiosk shutdown crash: The older compositor crash occurred
     during product-triggered session teardown, but inside external
     GNOME Kiosk/Mutter code. It needs separate reproduction and
     root-cause analysis.

  A fix should not globally disable Apport, delete crash reports, or
  alter reporting for ordinary users. It should prevent window-
  producing crash notification units from entering this specific
  restricted session.

  The investigation should also audit other globally enabled user-
  systemd units. Logs showed that the kiosk session inherited more
  than the three declared product components, so fixing only one
  notifier may leave the broader “complete application set” contract
  inaccurate.

  ## Continuation prompt

  Recommended model: Astra, high effort.

  > Investigate and, if justified by the evidence, fix the restricted
  > kiosk session allowing Ubuntu systemd user services to display
  > unrelated windows.
  >
  > Start with docs/System-Design.md, docs/SystemDesign/Frontends.md,
  > docs/SystemDesign/Lifecycle.md, docs/Approval-Tools.md, and the
  > repository AGENTS.md. Preserve all existing work and follow the
  > approval and VM-observation contracts.
  >
  > Evidence already established:
  >
  > - On Saturday 2026-09-19 around 14:05 PDT, the dedicated kiosk
  >   session displayed Ubuntu’s generic Apport dialog.
  >
  > - Photos are /home/edgar/pCloudDrive/IMG_1136.HEIC and /home/
  >   edgar/pCloudDrive/IMG_1138.HEIC. They show ExecutablePath: /
  >   usr/bin/gnome-kiosk, SIGSEGV, and crash date Fri Sep 11
  >   19:55:31 2026.
  >
  > - The report /var/crash/_usr_bin_gnome-kiosk.1002.crash was born
  >   on September 11. It was an old, unseen report—not a Saturday
  >   crash.
  >
  > - On Saturday, update-notifier-crash.path started with the kiosk
  >   graphical session. At 14:04:35, update-notifier-crash.service
  >   found the old gnome-kiosk report and launched apport-gtk. The
  >   service ended at 14:06:14.
  >
  > - The active Saturday GNOME Kiosk PID 6257 stayed alive until the
  >   successful request intentionally returned to login at 14:06:17,
  >   then stopped normally.
  >
  > - The September 11 crash happened during session teardown after
  >   the product app exited successfully. GNOME Kiosk asserted
  >   CLUTTER_IS_SEAT (seat) and segfaulted in libmutter-18.so. Treat
  >   this as a separate external-compositor investigation.
  >
  > Relevant product files:
  >
  > - data/gnome-session/sessions/oh-no-parent-control.session
  > - data/systemd/user/gnome-session@oh-no-parent-control.target.d/
  >   session.conf
  >
  > - data/systemd/user/oh-no-parent-control-app.service
  > - data/systemd/user/oh-no-parent-control-polkit-agent.service
  > - kiosk/oh_no_parent_control_kiosk/main.py
  >
  > Relevant installed Ubuntu files:
  >
  > - /usr/lib/systemd/user/gnome-session.target
  > - /usr/lib/systemd/user/gnome-session@.target
  > - /usr/lib/systemd/user/graphical-session.target
  > - /usr/lib/systemd/user/graphical-session.target.wants/update-
  >   notifier-crash.path
  >
  > - /usr/lib/systemd/user/update-notifier-crash.path
  > - /usr/lib/systemd/user/update-notifier-crash.service
  > - /usr/lib/update-notifier/update-notifier-crash
  > - /usr/share/apport/apport-checkreports
  > - /usr/lib/python3/dist-packages/apport/fileutils.py
  >
  > Confirmed mechanism:
  >
  > - Kiosk=true suppresses XDG autostart desktop files only.
  > - The product session still requires GNOME’s ordinary session
  >   targets.
  >
  > - gnome-session.target pulls in graphical-session.target.
  > - Ubuntu globally enables update-notifier-crash.path for
  >   graphical-session.target.
  >
  > - That path watches /var/crash; when triggered, it scans all
  >   accessible unseen .crash files and launches apport-gtk.
  >
  > - Therefore a non-product GTK window can appear above the
  >   fullscreen request station.
  >
  > Determine the correct scoped design before editing. Candidate
  > directions include a product-session conflict against both
  > update-notifier-crash.path and update-notifier-crash.service, or
  > another session-specific exclusion. Do not globally disable
  > Apport, modify Ubuntu-owned units in place, delete reports, or
  > affect ordinary accounts/sessions. Audit other globally enabled
  > graphical-session units capable of producing UI so the documented
  > request-only/complete-application-set guarantee is accurate
  > rather than fixing only the observed notifier by accident.
  >
  > Add regression coverage that proves the selected systemd
  > contract. Installed qualification should establish that a
  > qualifying stale kiosk-user crash report cannot create an
  > external dialog, the public request form remains the only
  > intended interactive surface, authentication still works, and
  > normal return-to-login remains clean. Internal crash-report setup
  > is engineering/system-test work, not a customer UI action. Any VM
  > work must use watchvm, the shared lease, guarded command
  > transport, and a published nonsecret operation intention.
  >
  > Separately assess whether the September 11 GNOME Kiosk/Mutter
  > shutdown SIGSEGV is reproducible with current packages. Do not
  > conflate that external compositor defect with the stale-dialog
  > isolation fix.
  >
  > If systemd session units change, classify activation under docs/
  > Publishing.md; this is expected to be session-renewal, with no
  > saved-data migration. Update the owning design documentation and
  > verify the appropriately scoped unit/system/UI tests.