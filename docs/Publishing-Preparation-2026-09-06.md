# Publishing preparation — 2026-09-06

## Follow-up: preparation outside test automation

The following work was completed after the initial rehearsal below:

- Git push authentication was exercised with `git push --dry-run --no-verify`
  against the intended SSH remote and `HEAD:main`; it succeeded without a
  remote change. Signing final source and tags remains a release-time operation.
- Quill 2.0.3's four bundled files match the official npm archive; the archive
  matched its published SHA-512 integrity. Monocraft font/license Git blob IDs
  match pinned upstream source. The Thunderbird image and notice match Mozilla's
  published files. Exact file identities and evidence links are recorded in
  [Asset-Provenance.md](Asset-Provenance.md).
- `NOTICE` and `Compliance.md` now cover Quill and Thunderbird. The Debian
  copyright record includes the full BSD-3-Clause conditions/disclaimer and
  references Ubuntu's locally installed full MPL-2.0 license.
- Removed four tracked generated Debian files identified below and added an
  ignore pattern for generated Debhelper snippets. Debhelper will regenerate
  them during normal package construction. This changes source hygiene only;
  no runtime integration, activation mapping, or saved-data migration changes.
- Staged `_install-product-files` under `/tmp/onpc-publishing-payload-20260906`
  successfully, without installing the product on the host. Ten legal files
  matched their sources with mode 0644; hashes of all 132 staged files were
  recorded in `/tmp/onpc-publishing-payload-20260906-manifest.json`.
  Debhelper's eventual installed `copyright` file and final `.deb` still need
  the binary-build track. The revised extension NOTICE follows the existing
  extension payload's `session-renewal` classification; standalone documentation
  updates require no process activation.
- Focused existing packaging, About-dialog, and publishing-helper checks passed:
  `tests/unit/test_installer.py`, `test_about_dialog.py`, and
  `test_publish_release.py`: **23 passed**. No test-automation implementation
  or aggregate test run was started.
- Rebuilt the unsigned source package with these packaging/legal changes in
  `/tmp/onpc-publishing-prep-final-20260906/source`, using recorded base-commit
  inputs plus only the preparation overlay. Concurrent setup/test work was not
  included. Source build passed; Lintian exited 0 with only the previously
  documented policy-version warning. All 298 archived files matched the
  snapshot's bytes and exact numeric modes, with no duplicate entries or
  unexpected file types. `inputs.json` and `source-review.json` beside the
  artifacts record scope and hashes. These are unsigned rehearsal artifacts.
- Reviewed the Malcontent integration against installed Ubuntu 26.04 public
  interface XML and timer-daemon introspection. SessionLimits `LimitType`,
  `DailyLimit`, `ActiveExtension`, AppFilter `(bas)`, timer `QueryUsage(uss)`
  returning `a(tt)`, and child `GetEstimatedTimes`/`EstimatedTimesChanged` match
  the application's adapters. Dependencies remain external; no vendored
  Malcontent implementation was found in the reviewed product payload.
  This confirms interface use, not runtime security acceptance.
- Reviewed the public help and privacy pages. Help describes the current
  local-control flow and bounded app-matching claims. The privacy page still
  denies all app-to-publisher transmission despite the implemented feedback
  feature. Prepared [replacement wording](Privacy-Notice-Release-Draft.md),
  including diagnostic logs being attached by default and removable before
  sending. No website change or feedback submission was performed.

**Publisher clarification on 2026-09-06:** the publisher confirmed creating the
product music and artwork using ChatGPT. This resolves the asset-origin question;
[Asset-Provenance.md](Asset-Provenance.md) records that statement separately from
verified third-party sources.

**Feedback policy resolved by publisher instruction:** the Parent App and local
documentation use this disclosure, also supplied to the separate portal session
for the website and operations guide:

> Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support. Retention depends on our support mailbox and service providers, including their backup policies. We do not currently guarantee deletion within a fixed period.

The prepared privacy-page draft reflects this policy. Publication of the portal
changes is handled in the separate session; confirm that page before release.
The remaining binary build/inspection and runtime acceptance depend on the
excluded test-automation work.

The initial rehearsal below remains historical evidence for its stated commit.

Preparation is complete to the extent supported by the current build. This is
not release acceptance. No release commit, version bump, tag, signing, source
push, PPA upload, product installation, or guarded VM run was performed.

## Source and evidence

The rehearsal used committed source
`2db2d9d5a86a6a1de504586b5fb4e057f358ca45` in an independent clone at
`/tmp/onpc-publishing-prep-20260906/source`. Uncommitted test-automation work
was deliberately excluded. Development subsequently advanced to
`f9bae49189f99eec3a3dcdad1935bb85b8f93a64`; these results do not certify that
newer commit. The checkout guards and affected assertions remain present there.

Local rehearsal logs and unsigned artifacts are retained under
`/tmp/onpc-publishing-prep-20260906/`. Temporary storage is not a durable release
archive; preserve any needed diagnostics before it is cleared. No `release.json`
was created because this was a rehearsal of product version `1.0`, not the
selection or freezing of a PPA release.

## Prerequisites checked

| Check | Result |
| --- | --- |
| Host | Ubuntu 26.04.1 LTS, `resolute`, `amd64` |
| Declared build dependencies | `dpkg-checkbuilddeps` passed |
| Publishing tools | `debuild`, `dput`, `dch`, `lintian`, `gpg`, `git`, and `dpkg-buildpackage` available |
| Publisher key | Recorded secret key available through GnuPG; fingerprint `4449F02C3E57F8215261A57958109B593907EFDE` |
| Launchpad registration | Public account GPG-key collection contains the same fingerprint |
| PPA | Public, active, publishing enabled; enabled processor collection contains only `amd64` |
| PPA archive signing key | Not assigned yet; consistent with a new unpublished archive |
| Public source | GitHub API reports public visibility and default branch `main` |
| SSH repository access | `git ls-remote` succeeded and remote `main` matched the rehearsal commit at the time of checking; no remote tags were returned |
| Version planning | Read-only `python3 tools/publish_release.py plan` proposed `1.0+ppa1~ubuntu26.04.1` |

The proposed version is not reserved. Fetch current remote history/tags and
query PPA publication history again at release time, including uncertain
pending uploads. Read access does not prove Git push permission. Secure signing
and upload authorization still need verification for the concrete final release.
No tools or host packages needed installation.

Public evidence endpoints used:

- [PPA configuration](https://api.launchpad.net/devel/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control)
- [Enabled processors](https://api.launchpad.net/devel/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control/processors)
- [Registered publisher key](https://api.launchpad.net/1.0/~puffyslipperstechllc/gpg_keys)
- [Public repository metadata](https://api.github.com/repos/Puffy-Slippers-Tech-LLC/parent-control)

## Binary rehearsal: blocked by test portability

Before building, the six isolated cleanup-safety modules specified in
`tests/README.md` passed: **49 tests and 3 subtests**.

`dpkg-buildpackage --build=binary --no-sign` invoked the declared `make check`
test gate. The initial sandboxed attempt had 10 failures and 881 passes;
`binary-build.log` preserves that attempt. A retry outside the sandbox resolved
the fixture's D-Bus failure, leaving **9 failures and 882 passes** in
`binary-build-unsandboxed.log`. Both builds exited 2. No `.deb` was produced.

The remaining failures are:

- `tests/unit/test_prepare_host.py`: missing-tool diagnostic, accepting an
  installed product on the host, and dispatch while capture blocks (3 cases).
- `tests/unit/test_system_runner.py`: selected execution prerequisites (1),
  missing `dpkg-deb`/`dpkg-query` diagnostics (2), and unavailable artifact
  diagnostics (3).

These tests reach production entry points whose fixed-checkout checks reject
the independent build directory with `guard:checkout` before the behavior under
test executes. This is a concrete clean-build portability blocker. Resolve the
unit-test isolation/build portability issue while retaining the real installed
runner's fixed-host guards. Do not bypass those guards, relocate Launchpad's
build to the development path, or use `nocheck` to obtain a publishable binary.
This preparation did not start the separate test-automation implementation
backlog or alter concurrent development.

Binary Lintian, installed payload inspection, package hashes, and guarded VM
validation remain unavailable for this rehearsal because the binary build failed.

## Unsigned source rehearsal

A separate source-only clone at `clean-archive/source` was built with
`dpkg-buildpackage --build=source --no-sign`. That standard command cleans before
archiving and passed. `lintian` on the resulting `_source.changes` exited 0,
reporting only `newer-standards-version 4.7.4 (current is 4.7.3)`, already
documented in `Publishing.md`. Recheck policy at actual release time.

An earlier direct `dpkg-source -b` diagnostic demonstrated why cleaning matters:
temporary Debhelper output produces Lintian errors. Its diagnostic logs remain
available; use the cleaned build's results below. The repository currently
tracks four generated Debian files that the normal clean step removes:
`debian/files` and the three `debian/oh-no-parent-control.*.debhelper` files.
They are generated packaging output, not missing corresponding source.

The cleaned archive comparison checked every archived file against Git blobs,
duplicate/extra entries, executable status, and symlink type/target. All 291
archived files matched; the four generated files above were the only exclusions
from the 295 tracked files. Build/install/migration scripts and bundled legal
records were included. Exact numeric archive permission modes have not received
the final source-mode review. No signature validation was claimed.

SHA-256 for the cleaned unsigned rehearsal artifacts:

| Artifact | SHA-256 |
| --- | --- |
| `oh-no-parent-control_1.0.tar.xz` | `d9f2455a5fa5106664fa26c810658de1e3f02dd9f464e57bd9d73609cbd1a50f` |
| `oh-no-parent-control_1.0.dsc` | `d95932104b5d850c50c8032ad01e6f4352de13984843f695ae8babbeb8221e60` |
| `oh-no-parent-control_1.0_source.changes` | `65044be7e7cde331e8bc5eca2ec92316c73cc0ba34b48de555f556dc1eba6bdd` |
| `oh-no-parent-control_1.0_source.buildinfo` | `ab3544b5dd284b4f0863812920c1190e7c5e45e00de9706ee3c0f3f925fac043` |

These files are preparation evidence, not upload candidates. The detailed
comparison is `clean-archive/unsigned-source-review.json`.

## Compliance preparation

The source review found GPL license/copyright/notice records, dedicated
Monocraft OFL, Quill BSD, and Thunderbird MPL copyright stanzas, and accompanying
bundled license records. The Makefile installs the product notices, font license,
editor license files, and Thunderbird branding notice. Its extension payload
includes GPL, copyright, and NOTICE. Actual binary installation remains to verify.

The shared About implementation includes License and Legal notices links,
GPL-3.0-only/no-warranty text, and the Malcontent non-affiliation disclosure.
This was a source review; both actual front-end displays remain to verify.

Open records and reviews:

- Retain provenance/permission evidence for `data/Gearbox_Waltz.mp3`, company and
  product logos, kiosk backgrounds, avatars, and other image assets. The general
  company copyright stanza does not document their creation or acquisition.
  The publisher was asked where this evidence is recorded; no origin or rights
  were inferred from filenames.
- Reconcile the compliance guide's bundled-asset discussion with the Quill and
  Thunderbird records already present in `debian/copyright`; confirm notices
  and complete applicable license texts in the final distribution.
- Perform the final supported-Malcontent-API and no-vendored-Malcontent review,
  review enforcement claims against `Threat-Model.md`, and review actual personal
  data handling if publishing a privacy notice. This preparation does not claim
  a complete legal, API, privacy, or security audit.
- Verify exact public release tags and source retrieval once the release is
  frozen. Today's public development branch does not establish release-tag
  availability.

## Draft release text — not for publication yet

Oh No! Parent Control 1.0 provides an administrator application for managing
child screen time and application access on Ubuntu 26.04 LTS. A child-session
GNOME Shell extension shows remaining time, and a shared request form lets
children request additional access from the overlay or kiosk session. This
initial package targets amd64 and integrates with the operating system's
Malcontent service. Review the product's documented enforcement boundaries
before deployment.

After successful PPA publication, the installation instructions are:

```sh
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo add-apt-repository ppa:puffyslipperstechllc/oh-no-parent-control
sudo apt update
sudo apt install oh-no-parent-control
```

Follow the package's reboot notice. These commands were drafted from
`Publishing.md` and were not executed on the host.

## Final release evidence template

Copy this table into the report beside the future `release.json`; fill every
field using that release's exact source and artifacts.

| Field | Required evidence |
| --- | --- |
| Source | Commit, reviewed inputs, remote reconciliation, signed product/package tags and fingerprints |
| Version | Product/PPA versions, fresh publication history, uncertain-upload check |
| Environment | Ubuntu release, architecture, build dependencies/tool versions, supported matrix |
| Safety | Isolated cleanup prerequisites, commands and outcomes |
| Binary | Clean build command/log, `.deb`/`.changes`/`.buildinfo` hashes, metadata and payload inspection |
| Acceptance | Exact-source host/UI/guarded-VM results, expected/executed coverage and unresolved gaps |
| Source upload | Signed source artifact hashes, `inspect` report, archive exclusions/modes/symlinks and Lintian review |
| Compliance | Asset provenance, complete notices/licenses, actual About dialogs, exact public source retrieval |
| Release decision | Publisher's readiness decision and concrete publication authorization |
| Publication | Exact source/build/binary statuses for every enabled architecture, final PPA/tag URLs and install commands |

Comprehensive `test-all` and graphical E2E acceptance remain unfinished according
to the current guide. Do not replace these fields with rehearsal results or
claim release readiness from a source archive or focused checks alone.
