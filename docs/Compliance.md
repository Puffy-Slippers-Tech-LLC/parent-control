# Compliance guide

This document is the maintainer guide for releasing and distributing Oh No! Parent Control. It explains the licensing and notice obligations for this product; it is not legal advice.

The short, user-facing notice is `NOTICE`. It must be shipped with every distribution. The canonical license and copyright records are `LICENSE`, `COPYRIGHT`, and `debian/copyright`.

## Scope and boundaries

Keep these topics separate so that each statement is accurate and reviewable:

| Topic | Canonical document | Purpose |
| --- | --- | --- |
| Licensing, notices, source availability, and third-party assets | This document and `NOTICE` | Distribution compliance |
| Security assumptions, enforcement boundaries, and mitigations | `Threat-Model.md` | Technical security claims |
| Personal data, logging, retention, and access | Product privacy notice, if one is published | Privacy obligations |

This guide may link to the threat model when describing a technical limitation, but it must not present a security property as a license term. Likewise, a privacy notice must describe actual data handling rather than copyright or third-party license information.

## Product license and corresponding source

Oh No! Parent Control is licensed as GPL-3.0-only. Every source and binary distribution must preserve the copyright notice, GPL license text, and warranty disclaimer. A recipient of an object-code distribution must be able to obtain the complete corresponding source, including package build, installation, migration, and deployment scripts.

The public source location is:

<https://github.com/Puffy-Slippers-Tech-LLC/parent-control>

Before publishing a release, make sure that location contains the exact source for the release tag and remains available for as long as the binary release is offered. Do not describe the product as proprietary or use an unqualified “All rights reserved” notice: that conflicts with the GPL permissions granted to recipients.

The parent and kiosk/child-overlay About dialog must continue to display:

- the product copyright holder;
- GPL-3.0-only and the no-warranty statement;
- a local path to the full license and legal notices; and
- the Malcontent attribution and non-affiliation disclosure.

## Malcontent integration

Malcontent is an independently installed operating-system dependency. The product communicates with it through documented public D-Bus and AccountsService APIs. It must not vendor, copy, patch, or redistribute Malcontent code or libraries unless this guide, `NOTICE`, the package metadata, and the licensing review are updated first.

The current Ubuntu-supported Malcontent package is LGPL-2.1-or-later. Because the product neither incorporates nor redistributes it, Malcontent’s own source, copyright notices, and license are supplied by the operating-system distribution. The product’s GPL-3.0-only license therefore applies to this repository and its shipped product files, not to Malcontent.

Do not claim that the product is affiliated with, endorsed by, or sponsored by the Malcontent authors or GNOME. Do not claim that Malcontent alone prevents every possible way to use a device or application. The specific technical boundary is documented in `malcontent014-integration.md` and the broader enforcement limitations are in `Threat-Model.md`.

## Third-party and bundled assets

Every file distributed in a release needs a documented provenance, copyright holder, and license or other written distribution permission. Record those facts in `debian/copyright` and preserve license texts or attribution notices where their license requires them.

The currently bundled Monocraft font is licensed under SIL OFL-1.1. Its copyright notice and complete license must remain alongside the installed font at `fonts/OFL.txt`. Before adding an image, sound, font, code sample, or other asset, obtain and retain evidence that the vendor has the right to redistribute it under the planned terms. Do not rely solely on a filename, embedded metadata, or a web search result as proof of redistribution rights.

## Debian package requirements

`debian/copyright` is the machine-readable package copyright record. It must cover every distributed file class, identify the upstream source, and include or reference the required license text and notices. The built package must install it as `/usr/share/doc/oh-no-parent-control/copyright`.

The package also installs the product license, copyright, `NOTICE`, README, and Malcontent integration note under `/usr/share/doc/oh-no-parent-control/`. The extension payload includes the GPL text, copyright, and notice because it may be distributed separately from the main package.

## Release checklist

Before releasing a source archive, Debian package, extension archive, or other binary distribution:

1. Confirm the release tag contains complete corresponding source and that the public source location serves that tag.
2. Review `debian/copyright`, `COPYRIGHT`, and `NOTICE` for every changed code or asset file; add a specific stanza for every third-party item.
3. Verify required license texts and attributions are installed with the package and, where applicable, the extension archive.
4. Confirm the About dialog still offers the local License and Legal notices entries and displays the GPL/no-warranty and Malcontent disclosure.
5. Reconfirm that all Malcontent interaction uses public supported APIs and that no Malcontent source, library, private API, branding, or endorsement claim was added.
6. Review `Threat-Model.md` for any changed enforcement claim and update a separate privacy notice for any changed collection, storage, retention, or disclosure of personal data.
7. Run `make check` and stage the package installation to verify the installed documentation paths.
