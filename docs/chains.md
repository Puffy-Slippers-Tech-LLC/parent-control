# Kiosk gateway chains handoff

## Requested change

Add four Minecraft-style chains to the kiosk drawing. Each chain must connect
one projected corner of the request form to the corresponding inner corner of
the gateway. The chains should feel native to the existing neon, pixel-art
gateway scene and must remain aligned when the window size or aspect ratio
changes.

The corrected chain implementation is complete. `GatewayAlignedRequest` now
derives the projected form corners from the final GSK allocation transform,
including its yaw, and paints four responsive, alternating block-built Cairo
link sequences behind the form. A shared artwork-geometry helper keeps the
gateway endpoints aligned with the JPEG's cover scaling and horizontal offset.
The terminal links overlap each attachment, with a deeper gateway-side inset so
the chain visibly emerges from beneath the inner frame instead of stopping at
its antialiased edge. Because the frame and opening are one background texture,
the chain layer is clipped to the measured opening polygon; the inset portion
therefore disappears beneath the frame instead of being painted over it. Links
follow a subtle gravity-sagged quadratic curve, have heavier metal sections,
and use a brighter violet/cyan portal palette.

Validation completed:

- All 114 tests pass through `make check`.
- Pure geometry and Cairo rendering checks pass at 1918×1443, 800×600, and
  2560×1080.
- A captured 912×1284 GTK preview reproducing the reported tall layout confirms
  that all four chains meet the form and are visibly inset into the gateway
  corners, remain behind the controls, sag naturally, and retain clear contrast
  in the violet/cyan portal palette.
- At 800×600, the pre-existing form's natural height exceeds the viewport and
  covers much of the behind-form chains. The chain geometry still recalculates;
  the production kiosk immediately fullscreens and is not affected.

## Repository and architecture context

Read `AGENTS.md` and `docs/System-Design.md` before continuing. Relevant
constraints are:

- The kiosk is the dedicated GTK request station.
- Its entry point is `kiosk/oh_no_parent_control_kiosk/main.py`.
- Fix the rendering in repository code so a clean installation reproduces it.
- Do not use legacy, private, internal, or hacky APIs.

The existing kiosk composition is code-native and should remain that way:

- `GatewayBackground` in `main.py` paints
  `kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg`, a vignette, and
  animated portal lightning using GTK snapshot and Cairo APIs.
- `GatewayAlignedRequest` projects the complete GTK request form into the
  gateway plane using a public `Gsk.Transform` perspective/rotation transform.
- `RequestWindow._build()` overlays `GatewayAlignedRequest` on
  `GatewayBackground`.
- `style.css` owns the form's visual styling.

The chain work belongs in the GTK snapshot/Cairo layer, not in the JPEG. This
keeps the chain endpoints attached to the live, responsive form and avoids
creating a second raster asset that only works at one resolution.

## Existing uncommitted work that must be preserved

At handoff, the worktree already had user changes in:

- `kiosk/oh_no_parent_control_kiosk/main.py`
- `kiosk/oh_no_parent_control_kiosk/request_content.py`
- `kiosk/oh_no_parent_control_kiosk/style.css`

Those changes are unrelated to chains. They add per-preview-account parent
control state, reject stale asynchronous preference responses, disable request
controls when screen-time limits are off, move the status label, and add error
styling. Do not revert or overwrite them. Inspect `git diff` before editing and
make only a narrow additive change.

## Existing rendering constants and behavior

`main.py` currently defines:

- `GATEWAY_CENTERING_OFFSET = 0.03125`
- `GATEWAY_FORM_YAW_DEGREES = 10.0`
- `GATEWAY_FORM_PERSPECTIVE_DEPTH = 1_200.0`
- `GATEWAY_FORM_CENTERING_OFFSET = 0.019`
- Preview size `1918 x 1443`

The background JPEG is `3840 x 2160`. `GatewayBackground.do_snapshot()` uses
cover scaling:

```python
scale = max(width / image_width, height / image_height)
```

It then horizontally shifts the rendered image by
`rendered_width * GATEWAY_CENTERING_OFFSET`. Any gateway endpoint calculation
must repeat that exact cover-scale and centering geometry so it agrees with the
painted image at all aspect ratios.

The inner opening-corner coordinates measured in the source JPEG are:

| Corner | Source pixels | Normalized image coordinate |
| --- | ---: | ---: |
| Top left | `(1374, 347)` | `(0.358, 0.161)` |
| Top right | `(2276, 405)` | `(0.593, 0.188)` |
| Bottom right | `(2276, 1780)` | `(0.593, 0.824)` |
| Bottom left | `(1374, 1837)` | `(0.358, 0.851)` |

Preserve the same ordering for the gateway corners and projected form corners.

## Recommended implementation

Keep the implementation in `kiosk/oh_no_parent_control_kiosk/main.py` and use
only supported GTK 4/GSK/Graphene/Cairo behavior.

1. Add constants for the artwork dimensions and the four normalized gateway
   inner corners.
2. Add a small helper that maps those normalized source-image points into the
   current widget allocation using the background's exact cover-scale,
   centering, and `GATEWAY_CENTERING_OFFSET` calculation.
3. In `GatewayAlignedRequest.do_size_allocate()`, use the final allocation
   transform plus `Gsk.Transform.transform_point()` to calculate the four
   projected form corners. Retain the resulting screen-space points on the
   widget so every attachment includes the same yaw and placement as the form.
   `Gsk.Transform.transform_point(Graphene.Point)` is available in the installed
   GTK bindings.
4. In `GatewayAlignedRequest.do_snapshot()`, append a Cairo node spanning the
   full widget allocation, draw the chains, then call
   `self.snapshot_child(self._child, snapshot)`. Drawing before the child makes
   the chains appear mounted behind the form while their other ends remain in
   front of the gateway artwork.
5. Draw a gently sagged chain between each corresponding gateway/form corner.
   Build each chain from repeated, overlapping angular hollow links rather than
   a plain line. Space links by sampled curve distance and orient each one to
   the local curve tangent. Alternate wide and narrow links to imply
   interlocking rings in perpendicular planes.
6. Scale link length and stroke width from the smaller window dimension, with
   sensible minimum and maximum values, so links remain legible at `800 x 600`
   and do not become enormous at high resolution.

Suggested visual treatment:

- Blocky, faceted link paths with pointed or stepped ends; avoid smooth oval
  jewelry-chain shapes.
- Near-black indigo outer stroke for separation from the background.
- Muted violet metal body with selective cyan edge highlights.
- A subtle purple/cyan glow behind the chain, much weaker than the animated
  lightning.
- Static chains. The existing lightning already supplies motion, and animating
  the anchors would make the mounted form feel unstable.
- Keep links hollow and overlap adjacent links enough to clearly read as a
  Minecraft-inspired chain rather than a dashed cable.

Do not use the image-generation skill for this task. The established asset is
already integrated into a responsive GTK drawing, and the chain endpoints must
follow live widget geometry.

## Tests to update

Extend `tests/unit/test_kiosk_rendering.py` with focused rendering-contract
checks. The current file uses source-level assertions for GTK rendering because
the unit suite does not construct a display. Cover at least:

- Four gateway inner-corner constants are present.
- The same background cover/centering math is used for gateway endpoints.
- Form corners are obtained with `projection.transform_point(...)`.
- A dedicated chain drawing method is called from
  `GatewayAlignedRequest.do_snapshot()` before `snapshot_child(...)`.
- The chain renderer creates alternating repeated links, not a single plain
  connector line.

Keep tests resilient: assert important public rendering behavior and named
helpers/constants, not every color literal or incidental loop spelling.

Run:

```sh
make check
```

Also run the preview:

```sh
make preview-kiosk
```

Visually verify all four links at both the default preview size and a smaller
window. Check that:

- Each chain touches the intended form and gateway corners.
- Chains do not cross form controls or obscure labels.
- Links retain the portal's perspective and pixel-art character.
- The bottom chains remain visible against the bright tiled floor.
- Resizing does not cause endpoints to drift.

## Preview/screenshot notes

The corrected tall-window preview was captured through public
`Gtk.WidgetPaintable` and `Gsk.Renderer` APIs. Its background, stack, and request
surface all reported the same `912×1284` allocation, confirming that the drift
was caused by the original artwork measurements rather than mismatched overlay
allocations.

## Files expected to change

- `kiosk/oh_no_parent_control_kiosk/main.py`
- `tests/unit/test_kiosk_rendering.py`

No JPEG or CSS change should be necessary unless live visual inspection reveals
a specific contrast problem that cannot be solved in the Cairo chain palette.
