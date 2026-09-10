# First release — publication handoff

**Publication is complete.** Verification succeeded on 2026-09-10 at
23:23:57 UTC: the exact binary is Published and indexed.
The indexed SHA-256 matches the accepted archive-built binary. No release gate
remains open, and no local monitor command or VM operation remains active.

## Current release

- Package: `1.0+ppa6~ubuntu26.04.1`, Ubuntu `resolute`, `amd64`.
- Published source commit: `2cfc450445ba1d2191b22b65c738e4a4f13bfa2c`.
- Public signed tag: `v1.0+ppa6_ubuntu26.04.1`.
- Frozen clone: `/tmp/onpc-release-20260910-ppa6/source`.
- Report, hashes and evidence: [release report](/tmp/onpc-release-20260910-ppa6/release-report.md).
- Launchpad source publication: `18726616`, Published.
- [Build 33587095](https://launchpad.net/~puffyslipperstechllc/+archive/ubuntu/oh-no-parent-control/+build/33587095):
  **Successfully built**.
- Binary publication: `249476130`, **Published** at 23:23:19.219565 UTC on
  2026-09-10; indexed package size: `4686698` bytes.
- SHA-256: `363a916a177eb5412f6de88632ce5408fa6fe6e5db40269927a12de22466d112`.
- Successful live output: [publication result](/tmp/onpc-release-20260910-ppa6/publication-result.json).

All required local acceptance is complete: signed-source inspection, full
archive binary build with 6,675 unit and 58 component tests, real sandboxed
Flatpak gate, binary/license review, and all four package installation/reboot
VM executions. Collection and baseline restoration passed. Launchpad also
passed its declared tests and completed the binary build. Preserve this evidence;
do not repeat validation merely because a new session begins.

## Next session

Start with: “Read docs/First-Release-Handoff.md and resume the release from the
completed publication checkpoint.”

Read the saved release report before selecting any further release work. The
publication date, indexed package identity, size and hash are already reconciled;
no client publication step remains pending. The temporary publication monitor
and its dedicated tests were removed at the user's request after success.
The release report and saved publication result remain intact as evidence.

Consumer commands are in the [release report](/tmp/onpc-release-20260910-ppa6/release-report.md#consumer-installation).
**First installation requires a reboot.** Portal readiness and comprehensive
graphical E2E coverage remain accepted gaps, separate from completed publication.

## Continuing boundaries

Publication and necessary release fixes remain authorized. **Ppa6 was uploaded
once successfully; never repeat its upload or move public tags.** Preserve the
frozen source and artifacts. Concurrent development changes to publishing/setup
helpers, tests and documentation are separate work; leave them intact.

Do not access or modify the portal, install the product on the host, or start
the accepted comprehensive test-all/graphical E2E backlog. If new signing becomes
necessary, follow [noninteractive signing](Publishing.md#noninteractive-signing);
never display/copy the real `.envrc` or prompt for a passphrase/readiness.

**Next-session settings:** `gpt-5.6-sol` / `high`; model: keep, effort: keep.
Reason: publication is verified; use the retained evidence to assess any newly
identified release follow-up. The accepted portal/E2E backlog is separate work.
