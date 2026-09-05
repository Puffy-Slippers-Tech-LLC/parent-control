# Floating kiosk and child crystals

The shared `GatewayBackground` animates the upper-left crystal, middle-left
island, lower-left island, and middle-right island. The gateway, blue square,
lower-right pedestal and foreground formations keep their original positions.

`kiosk/oh_no_parent_control_kiosk/floating_islands.py` retains the original
pixels from `kiosk-background-still.png` in cached GTK alpha-masked layers.
`kiosk/oh_no_parent_control_kiosk/kiosk-background-clear.png` supplies only the
small background regions exposed beneath these four silhouettes. Its masks
have a soft margin to remove the original edge glow without a hard seam. The
remaining scene continues to use the original still texture. Both images are
1672 × 941 and use the same responsive cover transform as the gateway.

Each formation starts at its own randomly chosen point along a path. At every
turn it samples a new height (6–13 pixels above or below its painted position
at an artwork height of 1080 pixels) and travel time (about 1.62–3.24 seconds to
the next turn). Quintic interpolation keeps position, velocity and acceleration
continuous through each reversal. There is no sine/cosine oscillator or repeated
animation clip. Monotonic elapsed time keeps speed independent of frame rate.

Lightning stores its source formation index and adds that formation's live
vertical offset on each frame, keeping the bolt attached to the moving tip.
Floating motion continues when sound and lightning are muted. Missing fill
artwork logs the asset name and error type and preserves the original static
scene with stationary lightning origins. No account information or per-frame
events are logged.

The Makefile installs the new fill image and Python module with the existing
kiosk payload. Both kiosk and child overlay use this implementation. The entire
installed kiosk directory already participates in the `session-renewal` update
activation digest; no new system integration, developer dependency or saved
data migration is required.

## Background fill provenance

The built-in imagegen tool generated `kiosk-background-clear.png` from
`kiosk-background-still.png`. The original asset remains intact; the generated
fill supplies the air and floor behind the moving layers. Prompt:

```text
Use case: precise-object-edit.
Asset type: clean background plate for independent crystal/island animation in an existing GTK scene.
Input image: edit target, the existing 1672x941 pixel-art gateway background.
Primary request: Remove exactly these FOUR formations and fill behind them seamlessly: (1) isolated upper-left floating crystal around x=190–300,y=90–235; (2) entire middle-left crystal island including rock base around x=84–268,y=313–558; (3) lower-left crystal cluster AND its complete stone island/pedestal around x=119–413,y=567–771; (4) entire middle-right crystal island including rock base around x=1244–1401,y=358–570. The first two and fourth leave dark navy air; the third should reveal matching continuous dark navy sky above and tiled floor below, with a clean undistorted sky/floor horizon matching the surrounding floor. Remove all four completely, including their glows and tiny dangling blocks.
Constraints: Preserve exact framing, aspect ratio, camera, composition, geometry, palette and all other objects. Keep the full central gateway unchanged; keep the upper-right pale blue pixel square, lower-right small purple crystal and its pedestal, foreground bottom-left crystals and foreground bottom-right crystals unchanged. Do not add stars, snowflakes, particles, text or watermark. Output the full frame at 1672x941 if possible. Only the four named formations are to disappear; the remaining artwork must match the input.
```
