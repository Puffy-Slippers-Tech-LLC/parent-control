# Resume first release publication

Resume [Publishing.md](Publishing.md). **Ppa5 failed on Launchpad after its tests
passed. Ppa6 is prepared with the missing build dependency and awaits signing.**

## Authorization and boundaries

- Publication, source pushes, PPA uploads and necessary release fixes remain
  authorized. Do not ask for publication permission again.
- Never prompt for the signing passphrase, open a passphrase dialog, or ask for
  clipboard readiness or another “go ahead,” including retries. The user replaced
  the old readiness requirement and configured `APT_PACKAGE_PRIVATE_KEY_PASSPHRASE`
  in the gitignored `/Data/Code/PST/parent-control/.envrc`.
- Read that file only inside the signing process, following
  [Noninteractive signing](Publishing.md#noninteractive-signing). Configure a
  batch/loopback GnuPG signer with private file-descriptor input for the ppa6
  commit, tag and source signatures; the variable alone does not configure GnuPG.
  Never expose its value in tool output, arguments, logs or chat, or copy `.envrc`
  into the release clone/archive. Missing or rejected values produce a redacted
  configuration error, never a prompt. No signing helper has yet been configured.
- Preserve existing public tags and accepted versions. Never retry ppa5's
  upload. Retain all its signed source, binary and VM evidence.
- The portal is accepted. **Do not check, modify or deploy it.**
- Use maintained helpers and normal sandbox escalation. Do not install the
  product on the host. The user accepted incomplete comprehensive test-all and
  graphical E2E coverage; do not start that backlog or repeat privacy/UI review.

## Exact current state — 2026-09-10

| Item | Value |
| --- | --- |
| Public and development main | `0d05af01d350e1cf067e444eba76101a20a04208` (ppa5) |
| Prepared correction | `1.0+ppa6~ubuntu26.04.1`, Ubuntu `resolute`, `amd64` |
| Ppa6 clone | `/tmp/onpc-release-20260910-ppa6/source` |
| Expected package tag | `v1.0+ppa6_ubuntu26.04.1` |
| Publisher key | `4449F02C3E57F8215261A57958109B593907EFDE` |
| Ppa6 preparation report | `/tmp/onpc-release-20260910-ppa6/release-report.md` |
| Ppa5 completed evidence/failure report | `/tmp/onpc-release-20260910-ppa5/release-report.md` |

Ppa6 was prepared automatically from the clean published ppa5 clone, then given
the reviewed correction and changelog entry. It has **no commit, tag, signature,
source/binary build, artifact build, VM run, push or upload yet**. No command
remains running. No VM operation remains active; ppa5's runner restored and
verified the accepted baseline.

Development retains the `debian/control` correction. Its publishing guide and
README now document noninteractive signing and manual `.envrc` setup. The user
added `.envrc.example` and the `.gitignore` entry for `.envrc`. These changes are
uncommitted; the prepared ppa6 clone still has the earlier documentation and
does not contain the new example/ignore entry. Synchronize these intended source
changes before freezing ppa6, preserving its versioned changelog. Keep the real
`.envrc` only in development. This handoff is an intentional untracked addition;
preserve it and do not silently include unrelated files.

## Proven failure and correction

[Ppa5 build 33587018](https://launchpad.net/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control/+build/33587018)
failed at 21:39:45 UTC after **6,675 unit and 58 component tests passed**.
Package staging then reported `glib-compile-schemas: not found`.
The command belongs to `libglib2.0-bin`, which was declared only as a runtime
dependency. Ppa6 adds it to `Build-Depends`; the publishing guide records
the failure and complete staging/debhelper acceptance boundary.

The remaining staging commands were audited against the standard build
environment and declared dependencies. Rendering and activation-manifest scripts
use Python's standard library. Runtime product code, runtime dependencies,
assets, licenses and saved-data contracts are unchanged.

Corrected development `make check` passed **6,675 unit and 58 component tests**
and all declared gates; log `/tmp/onpc-ppa6-working-check.log`.
`dpkg-checkbuilddeps`, changed Markdown links and `git diff --check` passed.
Do not repeat these merely because a new chat begins.
The subsequent signing-documentation/example/ignore changes do not invalidate
the product test results; check their links and source/archive handling. This
documentation update did not read the secret file or perform signing.

## Remaining work

1. Synchronize the intended source changes noted above, then configure
   noninteractive signing from the development `.envrc` and sign the prepared
   ppa6 release commit, package tag and source upload files. Do not ask for
   passphrase/clipboard confirmation. Retain public product tag `v1.0` and all
   previous package tags. Verify the secret file is absent from release inputs.
2. Inspect signatures and exact source archive using the release helper. Build
   the exact signed DSC without Git under a new versioned extraction directory,
   retaining output outside the clone. Run declared tests; do not use `nocheck`.
3. Run the separate `make check-test-fixtures` release gate with real sandboxed
   Flatpak launch. Its source/runtime behavior is unchanged; ppa5 results remain
   in the prior report. Keep this gate separate from Launchpad's portable tests.
4. From the frozen ppa6 clone build new artifacts with `tools/run-tests artifacts
   build`. From trusted development run `tools/run-tests system --artifacts
   <new-directory> --area package`. Require all four executions, collection and
   restoration. Do not substitute ppa5 artifacts.
5. Finish binary payload/license/Lintian review and hashes in the ppa6 report.
   Push normally, verify anonymous tagged-source retrieval, then upload once.
   Reconcile development's intended source edits before fast-forwarding it
   to the final signed release, preserving this handoff.
6. Monitor the exact source publication's `getBuilds` API result. Require
   **Successfully built**, then the exact amd64 binary **Published** and present
   in `resolute/main/binary-amd64` Packages. Source-only helper status is not
   sufficient. Never duplicate an uncertain upload.
7. Finish with PPA link, exact version, report, installation commands and the
   **required first-installation reboot**, then mark this handoff complete.

**Next-session settings:** `gpt-5.6-sol` / `high`; model: lower; effort: keep.
The failure is diagnosed and the dependency correction is settled. Raise to
Astra if new evidence requires difficult diagnosis or ownership review.

Public PPA: <https://launchpad.net/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control>.
API root: <https://api.launchpad.net/devel/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control>.
