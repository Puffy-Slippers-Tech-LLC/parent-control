# Shared request scene sizing — 2026-09-09

The reported laptop uses a 1920×1200 output at 125%, giving GTK a 1536×960
logical allocation. The developer machine has no installed app; reproduction
used the source previews on a private Wayland compositor. The user's later VM
screenshot supplied the visual reference: a complete form suspended inside the
gateway, clear upper/lower gaps, curved chains and visible crystal scenery.

## Cause and change

The previous geometry forced the gateway opening to 720 logical pixels and
stretched the entire background to accommodate it. That pushed the side islands
outside the laptop's viewport. The form was sized against the window rather than
the gateway opening, allowing it to overlap the upper and lower rails.

The shared implementation now fits the center and both side bands independently.
At the laptop allocation the outer gateway spans 40% of the width; a smaller
fraction would further constrain the form. Larger desktops cap its width at
640 logical pixels, while small windows allow a larger fraction. Floating
islands, lava, lightning endpoints and snow exclusions follow the corresponding
artwork geometry.

The form uses compact 14-pixel logical typography, bounded width, two duration
columns where space permits, and reduced duplicate CSS/widget margins. Its
projected bounds stay within the opening, reserving 7% of the opening's inner
height at both ends for chains. Normal and custom-duration forms fit without
scrolling at the reported laptop allocation. Expanded selectors and smaller
windows scroll inside a stationary frame.

The scrollbar uses GTK's supported
[external policy](https://docs.gtk.org/gtk4/enum.PolicyType.html) and a
[shared adjustment](https://docs.gtk.org/gtk4/class.Scrollbar.html). Its 2D
allocation follows the projected inset rectangle, keeping the narrow pointer
target aligned with the visible track. Real pointer tests exercise scrolling
through Mutter in both request modes.

Layout logs include logical allocation, board dimensions, integer monitor scale,
fractional surface scale, gateway width and chain clearance. They contain no
account names or identifiers.

## Verification

- `tools/run-unit-tests tests/unit/test_kiosk_rendering.py tests/unit/test_request_time_estimate.py tests/unit/test_kiosk_model.py -q --tb=line`: 50 passed, 7 subtests passed.
- `tools/run-ui-tests --timeout 240s tests/ui/test_request_layout.py -q -s`: 4 passed. Both request modes at 100% and actual 125% Wayland scaling, with 14 allocation passes and normal, custom and expanded states per combination. Checks include gateway containment, chain gaps, text sizes, complete footer reachability, scrollbar bounds and pointer targeting.
- `tools/run-ui-tests --timeout 240s tests/ui/test_request_form_component.py -k 'responsive_form_accepts_pointer_selection_and_submission or expanded_form_scrollbar_accepts_real_pointer_input or shared_custom_duration_preserves_fractional_minute_precision or result_action_uses_each_modes_exit_behavior or approval_uses_each_modes_result_exit_callback' -q --tb=short`: 10 passed, 48 deselected. Includes real mouse requests and scrolling, fractional custom minutes, result dismissal and approval callbacks in both modes.
- Each UI launcher completed its isolated cleanup prerequisites: 580 passed,
  3 subtests passed. Private application/compositor processes were cleaned up.

Retained layout evidence directories, in mode/scale order:

- Kiosk 100%: `/tmp/onpc-request-layout-7hft27on`
- Child 100%: `/tmp/onpc-request-layout-sg67mt43`
- Kiosk 125%: `/tmp/onpc-request-layout-7el9jwxm`
- Child 125%: `/tmp/onpc-request-layout-z0lk2046`

The laptop renders are named `laptop-request-1536x960-normal.png`,
`laptop-request-1536x960-custom.png` and
`laptop-request-1536x960-expanded.png`; each is 1920×1200 pixels. Kiosk custom
and expanded renders were visually inspected. The normal/custom scroll extent
equals its visible page (474 and 511 logical pixels respectively).

## Activation and scope

Source changes apply to both request surfaces and their result view. No saved
data or system integration changed; the existing kiosk `session-renewal`
classification is unchanged. New windows load the updated payload after a new
build is installed. This session did not install software, operate the user's
other laptop or VM, or modify the portal. Unrelated concurrent broker and test
changes were preserved.

See [front-end design](SystemDesign/Frontends.md#responsive-request-layout) for
the maintained layout contract.
