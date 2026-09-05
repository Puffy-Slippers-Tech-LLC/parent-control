# Kiosk snowflake background

The shared kiosk and child request screen uses
`kiosk/oh_no_parent_control_kiosk/kiosk-background-still.png` as its clean
background plate. `snowflakes.py` draws the floating pixel flakes independently,
with continuous slow paths outside the full gateway frame. The original
`kiosk-background.jpeg` remains available as the source artwork.

Flake pixel units are randomly sized from 0.9 to 6.6 pixels at 1920 × 1080,
scaling with the viewport; the upper bound is three times the earlier 2.2-pixel
maximum. Each flake keeps its size as it drifts. The primary drift cycles take
25–165 seconds, with a second wave adding gentle meanders. The shortest cycle
allows a maximum drift speed three times the previous 75-second minimum cycle.
Path amplitudes are chosen before their centers so flakes near the edges still
have room to move.
The exclusion margin includes the largest flake's halo.

The clean plate was edited with the built-in imagegen tool. The returned asset
is 1672 × 941 pixels; the original is 3840 × 2160. The renderer continues to use
the original artwork coordinate system for responsive cover scaling and gateway
alignment. The UI payload uses the existing `session-renewal` package activation
classification.

## Imagegen prompt

```text
Use case: precise-object-edit.
Asset type: clean background plate for a GTK kiosk/child app animation.
Input image: edit target, existing 3840x2160 gateway artwork.
Primary request: Remove ONLY all the small isolated floating snowflakes, tiny plus-shaped stars, sparkles and single bright specks from the dark navy background outside the gateway. Fill those tiny spots seamlessly with the surrounding dark navy background. These small particles will be animated separately in code.
Constraints: Preserve the exact original composition, dimensions, camera, geometry, perspective, every edge and location of the gateway, neon frame, orange bands, crystal formations and pedestals, floor tiles, reflections, and the large pale blue pixel square in the upper right. Preserve the empty dark gateway opening. Do not move, resize, restyle, simplify, or repaint any physical object. Do not remove highlights that belong to physical crystals or the gateway. No new objects, particles, flakes, stars, text or watermark. Output the same 3840x2160 full frame, with only those tiny floating background particles removed.
```
