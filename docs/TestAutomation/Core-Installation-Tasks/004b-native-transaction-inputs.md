# 004b — Implement verified native transaction inputs

Acceptance: host

Requires: 004a.

## Scope and prerequisites

Consume 004a's exact supported pairs below; do not substitute versions or
expand their transaction closure. Implement only their maintained
preparation, verification, staging and ownership, for both DEB and RPM.
Read [004's retained acceptance](../Core-Installation-Coverage-Handoff.md#task-004-final-native-update-acceptance),
[reusable preparation ownership](../../../tests/integration/Environment.md#reusable-preparation-ownership),
[VM baseline rules](../../Mandates/VM-Mandate.MD#vm-host-setup-and-baseline),
[storage allocation](../../Mandates/Test-Storage-Mandate.md#required-shared-allocation-routes)
and [host resource review](../../../tests/README.md#host-test-parallelism-review).
Inspect complete builder/staging/provenance functions and consumers before edits.

Extend existing input routes with finite native pair metadata, native signature
verification, architecture/version ordering, package and measured-file digests,
dependency closure and selected-input binding. Preparation owns reusable native
dependencies/fixtures; the deliberate old/new transaction remains attempt-owned.
Define how an old generation is established before retained admission without
turning a consumer into dependency repair or replacing the normal updated
baseline silently. Preserve unrelated native configuration and policy.

## 004a reviewed input selection

Reviewed 2026-10-18 against authoritative distro publication, build and package
metadata. These are finite input plans for **onpc-Ubuntu26.04** and
**onpc-Fedora44**, not installed acceptance. No VM mutation or native transaction
was performed. Cryptographic verification of the staged bytes, extracted-file
hashes and exact installed-baseline solver/trigger preflight are mandatory 004b
implementation gates; actual script/trigger execution and session recovery remain
004d acceptance. Refuse unavailable, substituted or incompatible inputs rather
than changing either pair or fetching additional packages during the history.

### Ubuntu 26.04: bubblewrap

| Input | Old | New |
| --- | --- | --- |
| Binary package / architecture | `bubblewrap:amd64` | `bubblewrap:amd64` |
| Native version | `0.11.1-1` | `0.11.1-1ubuntu0.3` |
| Origin | Ubuntu `resolute/main` Release | Ubuntu `resolute-security/main`; also published in Updates |
| DEB size | 50,622 bytes | 51,032 bytes |
| DEB SHA-256 | `090bb705b6d49213b288f19d78be78a55a1b72843efb12eae73ab5cca0f54b8d` | `d3a6c1b6b0e0474eaed6dbd055c0d601fd875af153976a0dc4aae75f4ea10868` |
| `/usr/bin/bwrap` ELF build ID | `975168fbb14fa09c3dd20125151089641969f717` | `38527d4f72857f1f39e1d6af03851b9dd831febc` |

Select the [old DEB](https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.11.1-1_amd64.deb)
and [new DEB](https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.11.1-1ubuntu0.3_amd64.deb).
The [Release Packages index](https://archive.ubuntu.com/ubuntu/dists/resolute/main/binary-amd64/Packages.gz)
and [Security Packages index](https://archive.ubuntu.com/ubuntu/dists/resolute-security/main/binary-amd64/Packages.gz)
give those exact sizes/digests. Launchpad records both the
[old Release publication](https://api.launchpad.net/1.0/ubuntu/+archive/primary/+binarypub/241198113)
and [new Security publication](https://api.launchpad.net/1.0/ubuntu/+archive/primary/+binarypub/249844811)
as Published for `resolute/amd64`.

The complete [old build log](https://launchpad.net/ubuntu/+source/bubblewrap/0.11.1-1/+build/32722232/+files/buildlog_ubuntu-resolute-amd64.bubblewrap_0.11.1-1_BUILDING.txt.gz)
and [new build log](https://launchpad.net/~ubuntu-security-proposed/+archive/ubuntu/ppa/+build/33605890/+files/buildlog_ubuntu-resolute-amd64.bubblewrap_0.11.1-1ubuntu0.3_BUILDING.txt.gz)
bind the distinct build IDs to each package's sole ELF, `/usr/bin/bwrap`,
root:root mode 0755, 80,424 bytes. The new binary retains the compiled
[ptrace fix](https://git.launchpad.net/ubuntu/+source/bubblewrap/plain/debian/patches/CVE-2026-41163.patch?h=applied/ubuntu/resolute-updates);
the [official changelog](https://changelogs.ubuntu.com/changelogs/pool/main/b/bubblewrap/bubblewrap_0.11.1-1ubuntu0.3/changelog)
distinguishes it from the later patch reverted in `.3`. This establishes changed
executable bytes, not merely different DEB metadata. Both report upstream version
`0.11.1`; `bwrap --version` cannot establish the native version or byte change.
004b must extract and record both executable SHA-256 values; this review did not
measure those SHA-256 values and does not invent them from build IDs.

Both controls require only `libc6 (>= 2.38)`, `libcap2 (>= 1:2.10)` and
`libselinux1 (>= 3.1~)`, with no Pre-Depends, Recommends, Breaks or lockstep
siblings. Release versions `2.43-2ubuntu2`, `1:2.75-10ubuntu2` and `3.9-4build1`
respectively satisfy them. The intended change set is **one DEB per phase**;
native offline simulation must prove installed dependencies and reverse
dependencies permit both versions, without any additional install, upgrade,
removal or dependency downgrade. Check package health and pending triggers first.
The Release/Updates/Security indexes also support the old version's principal
consumers: Flatpak `1.16.6-1` needs `>= 0.10.0~`; WebKit `2.52.0-1` and
`2.52.6-0ubuntu0.26.04.1` need `>= 0.3.1`; glycin-loaders
`2.1.1+ds-0ubuntu1` / `2.1.5+ds-0ubuntu0.2` and xdg-desktop-portal
`1.21.1+ds-1ubuntu3` / `1.21.1+ds-1ubuntu3.1` have unversioned requirements.
The Flatpak stanza is in the [Release universe index](https://archive.ubuntu.com/ubuntu/dists/resolute/universe/binary-amd64/Packages.gz);
the other current entries are in the main indexes above and
[Updates main](https://archive.ubuntu.com/ubuntu/dists/resolute-updates/main/binary-amd64/Packages.gz).
No reviewed consumer requires a companion downgrade; the actual installed-set
check still must detect third-party requirements, holds or later incompatibility.

Follow Ubuntu's [archive verification chain](https://documentation.ubuntu.com/security/software-integrity/archive-verification/):
native APT/`gpgv` verifies the pocket's InRelease with the trusted Ubuntu archive
keyring; its SHA-256 authenticates Packages, whose SHA-256 authenticates the DEB.
DEBs are not individually signed. Preserve the exact matching signed metadata
set in the input bundle; mutable index URLs alone are not evidence. The observed
[Release InRelease](https://archive.ubuntu.com/ubuntu/dists/resolute/InRelease)
binds Packages.gz size 1,874,082 / SHA-256
`73a7cee8168c3d3a72ef49e268b2cbb8e73652b732af6b074d632071e8e9c594`;
the observed [Security InRelease](https://archive.ubuntu.com/ubuntu/dists/resolute-security/InRelease)
(2026-10-17) binds size 739,864 / SHA-256
`055fbf29ad6ab2c8729da97735a4710b9a0cab2b18f7e8e6be45efbb19132836`.
A later valid index may differ, but must still bind the exact selected DEB.

The complete build-log control inventories contain only `control` and `md5sums`:
neither DEB has preinst/postinst/prerm/postrm or package-owned triggers. Both ship
`/usr/share/man/man1/bwrap.1.gz`. Ubuntu man-db's
[registered trigger](https://git.launchpad.net/ubuntu/+source/man-db/plain/debian/triggers?h=applied/ubuntu/resolute)
is `interest-noawait /usr/share/man`; its
[triggered postinst](https://git.launchpad.net/ubuntu/+source/man-db/plain/debian/postinst?h=applied/ubuntu/resolute)
runs `mandb -pq` through `setpriv` when `/var/lib/man-db/auto-update` exists,
otherwise records disabled database generation. Inventory the actual baseline's
matching triggers and exact owning versions before admission. Run normal dpkg/APT
trigger processing, retain its native output, independently check man-db's
applicable cache/result and no pending triggers, and preserve the disabled branch
when that is the verified baseline. Do not suppress triggers or infer their
execution from package version alone.

### Fedora 44: xdg-dbus-proxy

| Input | Old | New |
| --- | --- | --- |
| Name / epoch / architecture | `xdg-dbus-proxy` / `0` / `x86_64` | `xdg-dbus-proxy` / `0` / `x86_64` |
| Version-release | `0.1.6-4.fc44` | `0.1.9-1.fc44` |
| Origin | Fedora 44 release Everything | Fedora 44 updates Everything |
| RPM SHA-256 | `2197bd5a209e07c1a63bab22b0d1b262861186f850baa876a4bbcc3f916e9dbc` | `14827cdd90771c751cb8cabff0764b26821dc0cb4a7b617f0e033eabcab63b81` |
| `/usr/bin/xdg-dbus-proxy` SHA-256 | `1bfd8870b59939c54580bd7cb29ae7d2cffd8b348dbe9aeec7a3687e349e62c4` | `90d90a08aa46bc99b8fa226295be5869935e00a0f307f1dee4d78988e277d5af` |
| Executable size / owner / mode | 61,568 / root:root / 0755 | 65,728 / root:root / 0755 |

Select the [release RPM](https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/os/Packages/x/xdg-dbus-proxy-0.1.6-4.fc44.x86_64.rpm)
and [updates RPM](https://dl.fedoraproject.org/pub/fedora/linux/updates/44/Everything/x86_64/Packages/x/xdg-dbus-proxy-0.1.9-1.fc44.x86_64.rpm).
Their complete bytes were fetched and hashed; both match their respective
[old signed Koji copy](https://kojipkgs.fedoraproject.org/packages/xdg-dbus-proxy/0.1.6/4.fc44/data/signed/6d9f90a6/x86_64/xdg-dbus-proxy-0.1.6-4.fc44.x86_64.rpm)
and [new signed Koji copy](https://kojipkgs.fedoraproject.org/packages/xdg-dbus-proxy/0.1.9/1.fc44/data/signed/6d9f90a6/x86_64/xdg-dbus-proxy-0.1.9-1.fc44.x86_64.rpm).
Koji's [old file record](https://koji.fedoraproject.org/koji/fileinfo?rpmID=45848795&filename=/usr/bin/xdg-dbus-proxy)
and [new file record](https://koji.fedoraproject.org/koji/fileinfo?rpmID=48948870&filename=/usr/bin/xdg-dbus-proxy)
bind the executable hashes above to those exact RPMs. Independently hash extracted
payloads during 004b verification. [Bodhi's update record](https://bodhi.fedoraproject.org/updates/FEDORA-2026-93f562a43f)
records the new build signed and stable on 2026-10-01, with a logout suggestion;
that suggestion does not override the product's stale-manager recovery contract.

Use native RPM signature/digest verification against the trusted Fedora 44 key,
whose [official fingerprint](https://fedoraproject.org/en/security/) is
`36F6 12DC F27F 7D1A 48A8 35E4 DBFC F71C 6D9F 90A6`.
The [primary key asset](https://src.fedoraproject.org/rpms/fedora-repos/raw/f44/f/RPM-GPG-KEY-fedora-44-primary)
has SHA-256 `93642aec521a1e5e96dd715f7ae0ec0850ebc9de09a94ce03cae5263f26cc18a`.
Matching a signed-download directory is not cryptographic verification. Preserve
native verification receipts and trusted-key provenance in the bundle; never
import an arbitrary fetched key into the guest's system trust as a test repair.

The [old RPM requirements](https://koji.fedoraproject.org/koji/rpminfo?rpmID=45848795)
and [new RPM requirements](https://koji.fedoraproject.org/koji/rpminfo?rpmID=48948870)
are identical: `dbus`; 64-bit libc capabilities through `GLIBC_2.38` and
`GLIBC_ABI_DT_RELR`; libgcc `GCC_3.0`/`GCC_3.3.1`; `libgio-2.0.so.0`,
`libglib-2.0.so.0`, `libgobject-2.0.so.0`; `rtld(GNU_HASH)` and native RPM
compressed-filename/file-digest/zstd capabilities. Neither has conflicts,
obsoletes or weak dependencies. The intended change set is **one RPM per phase**;
native offline solver/capability and reverse-dependency preflight must refuse
additional changes. Record exact installed providers, not just SONAME presence.
The current Fedora 44 [Flatpak 1.18.4 spec](https://src.fedoraproject.org/rpms/flatpak/raw/f44/f/flatpak.spec)
requires `/usr/bin/xdg-dbus-proxy` without a version minimum;
[WebKitGTK 2.54.1](https://src.fedoraproject.org/rpms/webkitgtk/raw/f44/f/webkitgtk.spec)
requires the package without a version minimum; [Glycin 2.1.5](https://src.fedoraproject.org/rpms/glycin/raw/f44/f/glycin.spec)
requires bubblewrap instead. Thus the reviewed consumers admit old proxy 0.1.6
without companion downgrades; retain the installed-set preflight nonetheless.

The exact [old spec](https://src.fedoraproject.org/rpms/xdg-dbus-proxy/raw/54d2c192184b69b5351e3d068e79d23fe3bad280/f/xdg-dbus-proxy.spec)
and [new spec](https://src.fedoraproject.org/rpms/xdg-dbus-proxy/raw/8006c9fe8f6121751e45152ed9028d9da0a6fc70/f/xdg-dbus-proxy.spec)
declare no runtime scriptlets or package-owned triggers. Inventory installed
external file/transaction triggers and retain their exact owners/definitions.
The manpage matches Fedora 44 man-db's
[`%transfiletriggerin` / `%transfiletriggerpostun`](https://src.fedoraproject.org/rpms/man-db/raw/f44/f/man-db.spec)
on `/usr/share/man`, which request `man-db-cache-update` through systemd-run and
systemctl. Preserve ordinary RPM trigger execution. Native transaction records
plus independent service/journal/cache evidence must distinguish a successful
trigger request from completed cache maintenance; wait for applicable work to
finish and retain its result. Reconcile any other matching baseline trigger
before the attempt, without adding packages or suppressing native behavior.

### Old-generation preparation and finite expected results

Implement these checkpoints through the existing builder/preparation/staging
owners, not an alternate installer or general online updater:

1. Verify both artifacts, native version ordering, architecture, signatures,
   payload hashes, installed providers/reverse dependencies and complete matching
   trigger inventory. Bind the pair and preparation receipts to selected inputs
   and baseline provenance. These are read-only checks for consumers. A complete
   native old-version transaction, including any deliberate downgrade from the
   updated baseline, is an explicit owned scenario phase **before product
   admission**. It is not prerequisite repair and must never silently replace or
   downgrade the accepted baseline. Install the product through `make install`,
   finish initial configuration/reboot, and establish old generation A before
   retaining its manager/session. Recheck the old native identity after product
   installation/reboot; refuse if installation changed it. No automatic update
   may race the finite pair.
2. Use actual generation records from
   [`inventory()`](../../../tools/kiosk_confinement.py), not only the broader
   [`record_native_packages()`](../../../tests/integration/system_kiosk_confinement.py)
   diagnostic list. Fedora's target is the direct service executable. Ubuntu's
   `/usr/bin/bwrap` is the `bwrap-native` **source**, copied to private destination
   `/usr/libexec/oh-no-parent-control-kiosk-bwrap`; private `/usr/bin/bwrap` holds
   the product wrapper. Compare the correct substituted record/private path,
   not the unchanged wrapper, with host old/new bwrap bytes.
3. Before the native upgrade, retain a real long-lived owned native process
   mapping the selected old executable in generation A: a confined native bwrap
   bootstrap/monitor on Ubuntu and native xdg proxy on Fedora. 004c must compose
   these through supported finite role routes. Record PID/starttime/credentials,
   executable mapping device/inode/hash, enforcing label, namespace, generation
   and owning unit/session. A short `--version` call or namespace-file hash alone
   cannot establish retained **process mappings**. Keep allowed-service and
   ordinary-user positive controls and saved child policy as independent witnesses.
   Ubuntu's [native bwrap monitor](https://raw.githubusercontent.com/containers/bubblewrap/v0.11.1/bubblewrap.c)
   waits for its sandbox child; a finite `--block-fd` witness can retain it and
   then release the child to finish normally. Pin monitor and child separately:
   the `--info-fd` child PID is not the monitor PID. This route still needs 004c
   composition and installed qualification under the actual role policy.
4. Perform the exact new native transaction, with repositories unavailable and
   ordinary scripts/triggers enabled. Native package state and host payload hash
   must show B; independent retained mapping and private-tree evidence must stay
   A with unchanged owned process identities. Recheck every manager thread's
   credentials, enforcing role, namespace and generation. Require an allowed
   native service and a fresh forbidden-shell executor/kernel denial under that
   same manager, plus unchanged ordinary-user/vendor behavior and child policy.
5. Fresh GDM admission measures B and refuses retained manager A with
   `manager-generation-stale` / `stale-manager-reboot-required`, without restarting
   it or publishing B. Existing admitted execution of pinned A remains valid.
   This follows the [native generation contract](../../SystemDesign/Kiosk-Confinement.md#native-execution-and-executable-identity).
6. Independently hold a real native admission lease, then run the maintained
   policy-loader refusal probe: nonzero `kiosk-admissions-active`, same holder,
   PAM and confinement-state bytes, and continued enforcement. A retained manager
   alone does not prove a held lease. Once the lease drains, unchanged
   configuration/PAM may allow `load`; it reloads attested policy, not native
   inventory, and cannot make A current. Use
   [`verify_loader_admission_refusal()`](../../../tests/integration/system_kiosk_confinement.py).
7. Explicitly exercise the existing synchronous user-manager reexec protocol
   (`notify-reload`, signal 59) through the owned unit, separately from any native
   package trigger. Require the same manager identity, namespace, generation,
   enforcing label, pinned A bytes, allowed-service result and fresh shell denial,
   following `manager_boundary()` / `verify_updates()` in that same source.
   Neither chosen package claims to request this product manager reexec itself.
8. End the owned session normally and observe retirement without killing a
   manager to force inactivity. Logout can retain A. Follow the product's
   [stale-manager reboot boundary](../../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle):
   a real changed boot clears completed runtime generations; fresh native
   manager admission prepares B from verified new bytes. Prove fresh station
   admission, native enforcement, public broker operation and unchanged child
   policy. Native-only transactions do not inherently call product configure,
   policy load or create a product reboot marker; do not expect a restart modal
   from unrelated distro markers. Neither selected pair changes vendor PAM;
   preserve its exact configuration, and retain the original 004 obligations
   rather than claiming changed-PAM coverage from these executable-only pairs.

The existing released-product builder in
[`build_test_artifacts.py`](../../../tools/build_test_artifacts.py) builds pinned
earlier/current **product** packages only. It supplies neither native pair nor
these native signature/closure/trigger receipts. Extend maintained input routes
in 004b; do not mislabel its `--upgrade-inputs` output as this native input.
Any unavailable artifact, incompatible baseline or unaccounted trigger refuses
preparation with the exact identity and return condition, never a substitute pair.

## Acceptance and close-out

Focused host regressions must cover both formats, exact compatible inputs,
missing/tampered/same-byte/wrong-version or architecture refusal, staging
collisions, foreign/symlink ownership, interrupted retry and retention binding.
Cover preparation first/repeat/update/retry and read-only consumer verification
where affected. Review every applicable resource inventory and cleanup owner.
Publish the implemented invocation and manifest contract in its existing
builder/installed-environment owner; mark live qualification still pending.
No new generic package-update framework or alternate storage/installation route.

Run affected host checks, check Markdown/plan, and refresh generated inventory
if collection changes. Product/build-input changes require `make build`; report
missing prerequisites. Mark only 004b complete. Real transaction scripts,
retained mappings and admission recovery remain unqualified until
[004d](../Core-Installation-Coverage-Handoff.md#task-004d-native-update-qualification) passes on both targets.
