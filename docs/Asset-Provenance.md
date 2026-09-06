# Bundled asset provenance

Reviewed 2026-09-06. This records source identity and distribution notices;
final package inspection must confirm the matching files and notices ship.
`debian/copyright` remains the package license record. Do not place account
credentials, receipts containing personal information, or private contracts here;
record a non-sensitive reference to protected evidence instead.

## Verified upstream assets

- **Quill 2.0.3**: all four bundled files match the official npm distribution
  byte for byte. The downloaded tarball matched the registry's SHA-512 integrity
  `sha512-xEYQBqfYx/sfb33VJiKnSJp8ehloavImQ2A6564GAbqG55PGw1dAWUn1MUbQB62t0azawUS2CZZhWCjO8gRvTw==`.
  [Registry metadata](https://registry.npmjs.org/quill/2.0.3),
  [distribution archive](https://registry.npmjs.org/quill/-/quill-2.0.3.tgz),
  [source](https://github.com/slab/quill/tree/v2.0.3).
  BSD-3-Clause; Slab, Jason Chen, and salesforce.com copyrights are preserved.
- **Monocraft**: the font and OFL text match the upstream Git blobs at
  commit `e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9`:
  `dist/Monocraft-ttf/Monocraft.ttf` (blob `8b7e08a769fbe81babbecf95a9be9b5e99780ac5`)
  and `LICENSE` (blob `801ddb9e1f7fff3a60125ba8c2eac1db3f9d94c2`).
  [Pinned upstream source](https://github.com/IdreesInc/Monocraft/tree/e498bf70aeb25b4bdcff1e44d878fb2cb4f7c2a9).
  SIL OFL-1.1; Idrees Hassan's notice is preserved beside the font.
- **Thunderbird preview icon**: the image and branding notice match the
  Mozilla upstream files retrieved on 2026-09-06 byte for byte:
  [image](https://hg.mozilla.org/comm-central/raw-file/tip/mail/branding/thunderbird/default128.png)
  and [notice](https://hg.mozilla.org/comm-central/raw-file/tip/mail/branding/thunderbird/LICENSE).
  These upstream URLs move; the hashes below identify the reviewed bytes.
  MPL-2.0 and Mozilla's trademark reservation are recorded in `NOTICE` and
  `debian/copyright`. The unmodified icon identifies an application in preview
  data; it is not product branding. The same icon bytes ship in corresponding
  source. The full license is supplied by Ubuntu at
  `/usr/share/common-licenses/MPL-2.0`.

## Publisher-created music and artwork

On 2026-09-06, the publisher confirmed in the publishing-preparation conversation
that they created the product music and artwork using ChatGPT. This confirmation
covers the music, product/company logos, kiosk backgrounds, avatars, and timer
image listed below. It is the recorded source of the creation-method statement;
it is distinct from the byte-verified third-party assets above.

These files retain the repository's existing company distribution and
GPL-3.0-only declaration. This record documents provenance, not a determination
of copyright protection for AI-generated output. No ChatGPT plan, generation
date, or third-party input history was supplied, and none is invented here.
The publisher should retain the original generation conversations and editable
source materials with their project records. The timer image is tracked source
but is not currently selected by the extension's installation asset list.

## Reviewed file identities

Paths are relative to the repository root. `Verified upstream` means a byte
comparison succeeded; `Publisher-confirmed ChatGPT creation` records the
publisher's statement above.

| File | SHA-256 | Provenance status |
| --- | --- | --- |
| `child/remaining-timer-seconds.png` | `c1bd55f4d78b134d06d9c35dc9767131c23fa23390b4bd4092080776409454de` | Publisher-confirmed ChatGPT creation |
| `common/oh_no_parent_control_ui/test_user_icons/casey.png` | `6bb3b256585d0f969206e84c30f95d6745d78ab9e70c0eef1020ce3e03f1259f` | Publisher-confirmed ChatGPT creation |
| `common/oh_no_parent_control_ui/test_user_icons/jamie.png` | `0780e664851fa1370f64bf998ab17bff6047e65a717409ba8de5a855f5d63cf4` | Publisher-confirmed ChatGPT creation |
| `common/oh_no_parent_control_ui/test_user_icons/jordan.png` | `4fe03cf1c4be85dfc4d6bf7ce8a421e0dd0bb2769dae151dcb1563ed82d0473c` | Publisher-confirmed ChatGPT creation |
| `common/oh_no_parent_control_ui/test_user_icons/riley.png` | `8104883ab89947b32030fdc60655dcba866a0ac6dac591115141685f8210ebd2` | Publisher-confirmed ChatGPT creation |
| `data/Gearbox_Waltz.mp3` | `04613c843aab2e35d42ac380d5e4ff28e81b2583e028a08cd7ea4913eb6864f3` | Publisher-confirmed ChatGPT creation |
| `data/app_logo.png` | `e5dc43f93f2e6d7c53895d89f6227e24faab219f949203e8d807770eb049ada7` | Publisher-confirmed ChatGPT creation |
| `data/app_logo_gnome_launcher.png` | `bfbaa734bcc06c0ed9eef6063014aa14d66035e643dbb7724dc16583ae516795` | Publisher-confirmed ChatGPT creation |
| `data/app_logo_titlebar.png` | `26d5b9f465ce722ae731f285c6fc6018c3bac1de3eb1d7ea59d88e6d42930240` | Publisher-confirmed ChatGPT creation |
| `data/company_logo.png` | `727ccbcbd71a3dbfcf117dce68b38023bb8ab2351fa95f47afd3ffcd8c6a1b57` | Publisher-confirmed ChatGPT creation |
| `kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf` | `262e31822e0a75be567b02320bfa092143d871e8a273e529d1c5ab0c04cd215f` | Verified upstream |
| `kiosk/oh_no_parent_control_kiosk/kiosk-background-clear.png` | `a28ab4d148ab7376ba0662e3557498eafd5354fd2e703e57872d02f56ed54fb0` | Publisher-confirmed ChatGPT creation |
| `kiosk/oh_no_parent_control_kiosk/kiosk-background-still.png` | `e7e0e4fb6f9bd1365b69a868bdab1ecc8f3e83d66908a8fec43ddf6612935c1d` | Publisher-confirmed ChatGPT creation |
| `parent/oh_no_parent_control_parent/thunderbird-default128.png` | `64214367f8f8633e3a5be46b18d2bb608d7a76a45cdc5373a5da875013c6d600` | Verified upstream |
| `kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt` | `f69c147003e052dbc9d96c40a9f73647e72766cfda95a597b94ed827fe25acb1` | Verified upstream |
| `parent/oh_no_parent_control_parent/THUNDERBIRD-BRANDING-LICENSE` | `e2935aa5aec2b6d94179892965fc32b192e6ba9204e68595779b6b22c4f75d02` | Verified upstream |
| `parent/oh_no_parent_control_parent/rich_editor/quill.js` | `f6157c72ac9b3f51cdead426335688a027b12405d9d6a4daadd38a676b2d7ff2` | Verified upstream |
| `parent/oh_no_parent_control_parent/rich_editor/quill.snow.css` | `1c7948cd13aa92fac6390319bc1e5e461823da171519d3a768db56164f871636` | Verified upstream |
| `parent/oh_no_parent_control_parent/rich_editor/quill.js.LICENSE.txt` | `7b1938804d68d96764233d0a148a7501f39e547e6ae2dead4b16836e9b8d123c` | Verified upstream |
| `parent/oh_no_parent_control_parent/rich_editor/LICENSE` | `395c12b616d6f58238b4be39284d4d9221b58dd6e1f1e34d9ab537e34abbb022` | Verified upstream |
