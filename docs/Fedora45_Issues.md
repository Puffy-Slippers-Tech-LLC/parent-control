# Fedora 45 issues

## Native enforcement: incompatible fapolicyd magic database

Initial investigation date: 2026-11-04. Vendor retest: 2026-11-06. Status: the
reported native failure no longer reproduces with `fapolicyd-2.0.2-1.fc45` and
`file-libs-5.48-3.fc45`. Full VM preparation and installed-product compatibility
remain unqualified; this retest was limited to the vendor bug.

Reported to Fedora under the `fapolicyd` component as
[Bug 2568044: fapolicyd fails to start with file-libs 5.48: suspected compiled magic database format mismatch](https://bugzilla.redhat.com/show_bug.cgi?id=2568044)
on 2026-11-06 UTC. The report includes the native reproducer, package versions,
startup diagnostics and package-integrity verification without mentioning this
product. It describes the format mismatch as suspected and notes that
`fapolicyd 2.0.2` had not been tested when the report was filed. The subsequent
vendor retest is recorded below.

### Vendor-requested retest

Red Hat requested testing
[fapolicyd-2.0.2-1.fc45, FEDORA-2026-67d32ed434](https://bodhi.fedoraproject.org/updates/FEDORA-2026-67d32ed434).
On 2026-11-06, a diagnostic-only guarded preparation attempt on VM 30 compared
the retained failing package with that exact build:

| Check | Before update | After update |
| --- | --- | --- |
| fapolicyd | `2.0.1-1.fc45.x86_64` | `2.0.2-1.fc45.x86_64` |
| file-libs | `5.48-3.fc45.x86_64` | Unchanged |
| `fapolicyd-cli --ftype /usr/bin/true` | Exit 8, invalid offsets and `Cannot initialize file helper libraries` | Exit 0, `application/x-executable` |
| `rpm -V fapolicyd file-libs` after update | — | Exit 0, no differences |
| Compiled magic format after update | — | Version 21 |
| Native startup and readiness after update | — | Service enabled and active; `--check-status` passed; 31,044 rpmdb rows |

The guest command was
`dnf5 --refresh --enablerepo=updates-testing -y upgrade fapolicyd-2.0.2-1.fc45`.
DNF also upgraded `fapolicyd-selinux` to the matching build and replaced
`rpm-plugin-fapolicyd`, as declared by the vendor transaction. No magic database
substitution or policy bypass was used.

The probe stopped deliberately after native readiness, before baseline capture
or product installation. Its diagnostic-only exception makes the preparation
launcher report failure; it does not represent a failed native check. The
controller verified the VM powered off. Temporary diagnostic code was removed
from the checkout; retained guest staging and controller state remain available
through the guarded preparation route. No full preparation or installed-product
acceptance is claimed, and no bug-tracker reply was posted.

Private diagnostic log, subject to normal retention:
`output/test-runs/privileged/allocations/onpc-baseline-preparation-failure-jtspoamb/preparation.log`.

### Affected environment

| Item | Observed value |
| --- | --- |
| Registered VM | `30` / `onpc-Fedora45` |
| Daemon package | `fapolicyd-2.0.1-1.fc45.x86_64` |
| Native library package | `file-libs-5.48-3.fc45.x86_64` |
| Failing file | `/usr/share/fapolicyd/fapolicyd-magic.mgc` |
| Package integrity | `rpm -V fapolicyd file-libs` returned 0 with no differences |

The failing database and library match their installed RPMs. There was no
evidence of local file corruption or preparation overwriting the vendor database.
These observations describe the investigation's guest and repository state;
they are not a claim about every Fedora 45 installation or future updates.

### Observed failure

After the SSH parsing and GNOME settings-session fixes, preparation verified all
four test accounts and wrote its preparation record. Native initialization then
failed at `systemctl start fapolicyd.service`.

The daemon loaded its rules and initialized its trust database with 31,043
entries. Its journal reported:

```text
Trust database checks OK
/usr/share/fapolicyd/fapolicyd-magic.mgc, 1: Warning: offset ... invalid
Unable to load fast magic database
fapolicyd.service: Main process exited, code=exited, status=1/FAILURE
```

The trust database passed inspection. The separate compiled magic database,
used for file-type detection, failed to load. Deleting or rebuilding the trust
database would not address this observed failure.

### Cause and confidence

The retained invalid-offset bytes identify a compiled magic header containing
format version 20. Upstream `file` 5.48 defines compiled magic format version 21.
This strongly supports a compiled-database/library format mismatch as the cause.
See the [file 5.48 format definitions](https://github.com/file/file/blob/FILE5_48/src/file.h).

The exact vendor package-build mistake has not been independently established.
No replacement RPM has been rebuilt or qualified during this investigation.

### Product impact

The product RPM [requires fapolicyd](../rpm/oh-no-parent-control.spec.in).
[Package configuration](../packaging/lifecycle/postinst.in) starts native
enforcement services, and the [Fedora lifecycle integration](../packaging/fedora.inc)
requires execution-policy readiness to succeed.

The Fedora [readiness service](../data/systemd/fedora/oh-no-parent-control-execution-policy-ready.service)
requires `fapolicyd.service`. The product's
[display-manager integration](../data/systemd/fedora/display-manager.service.d/oh-no-parent-control.conf)
requires that readiness service before admitting graphical sessions. The native
policy contract belongs to [application enforcement](SystemDesign/Applications.md#live-filter-and-execution-rules).

Consequently, the same incompatible packages can prevent product configuration
or graphical startup from completing. This conclusion follows from the observed
native-service failure and the product dependency chain. A product installation
on VM 30 was not performed during this investigation, so this is not a claimed
installed-product reproduction.

A test-only database substitution, permissive policy, or skipped readiness gate
would hide the dependency problem rather than fix product compatibility.

### Repair attempted

Within guarded baseline preparation, the investigation:

1. Reproduced native-library failure with the public command
   `fapolicyd-cli --ftype /usr/bin/true`.
2. Verified that the installed vendor packages were unmodified.
3. Attempted `dnf5 --refresh -y upgrade fapolicyd file-libs`.
4. Repeated file-type inspection and queried available package versions.

The update did not change the installed versions, and file-type inspection still
failed. A refreshed query of the guest's enabled repositories offered the same
incompatible versions.

At initial investigation time, Fedora's source repository contained a newer
`fapolicyd 2.0.2` specification. This does not prove that a compatible binary was
available to this guest or that it fixes the problem. That version was untested
until the vendor-requested retest above. See the [Fedora 45 package specification](https://src.fedoraproject.org/rpms/fapolicyd/raw/f45/f/fapolicyd.spec).

The unsuccessful automatic-update implementation was removed. No substituted
database, enforcement bypass, permissive-policy workaround, or weakened
readiness check remains in the session's committed changes.

### Evidence and handoff

Historical private artifacts, readable through the maintained
[artifact reader](../tests/README.md#prompt-free-test-artifact-access):

- Native failure and package-integrity evidence:
  `output/test-runs/privileged/allocations/onpc-baseline-preparation-failure-o318sshf/preparation.log`.
- Update attempt and refreshed repository query:
  `output/test-runs/privileged/allocations/onpc-baseline-preparation-failure-iambgo_e/preparation.log`.

These are ordinary retained diagnostics, subject to normal retention, not durable
evidence archives. At handoff the VM was powered off and its snapshot and
controller state were retained. Continue through the maintained
[VM preparation and maintenance routes](Mandates/VM-Mandate.MD#owned-maintenance-and-execution);
do not discard recovery state to bypass the refusal.

The preceding fixes are committed in `9a7a7893`: case-insensitive OpenSSH keyword
parsing, local-VFS pre-login settings sessions, colored preparation outcomes,
and improved private diagnostics. SSH and account preparation passed live on
VM 30; source checks and independent review passed. Full preparation did not
pass, and the green final success line was not exercised end-to-end.

### Required resolution

The vendor retest passes the native checks below for the exact updated package
combination. Broader compatibility acceptance remains outside this retest and
requires:

1. Successful native file-type inspection.
2. Successful native daemon startup and readiness.
3. Complete guarded VM preparation.
4. Installed-product configuration and native enforcement checks using the same
   package combination, including the product's readiness gate.

Recommended continuation model: GPT-6.1 Sol xHigh for the unresolved vendor
compatibility diagnosis. Preserve the existing fixes and unrelated workspace
changes; no test-only workaround should replace product acceptance.
