# Shared request scenery

The child overlay and kiosk use the original pixels in
[kiosk-background-still.png](../../kiosk/oh_no_parent_control_kiosk/kiosk-background-still.png)
for the gateway, crystal formations, islands and moon. The eight silhouettes in
[floating_islands.py](../../kiosk/oh_no_parent_control_kiosk/floating_islands.py)
retain their source proportions with uniform scaling around their bottom
anchors. Four float; the remaining foreground formations, pedestal and moon
stay stationary. Lightning uses the same geometry and motion as its crystal.

The side backdrop is
[kiosk-background-scenery-clear.png](../../kiosk/oh_no_parent_control_kiosk/kiosk-background-scenery-clear.png),
a 1672×941 clean sky/floor plate generated with the **built-in imagegen tool**.
It fills the complete side bands, preventing stretched remnants or mismatched
erasure patches when silhouettes change size. Its central gateway pixels are
unused: the center band always uses the original artwork. The existing
[kiosk-background-clear.png](../../kiosk/oh_no_parent_control_kiosk/kiosk-background-clear.png)
was the edit input and remains in the checkout as source material.

The [Makefile](../../Makefile) installs the new backdrop beside the shared form.
It inherits `session-renewal` from the existing kiosk payload classification;
no classification or saved-data migration changes are needed. Source previews
watch the new filename and reload it when changed.

Regression checks cover uniform scale and silhouette containment across small,
portrait, laptop, conventional desktop and ultrawide allocations. Lightning
checks cover both fitted contacts and floating offsets. GTK layout and real
3840×1600 preview/production checks cover both shared request surfaces.

## Generation prompt

Edit target: `kiosk/oh_no_parent_control_kiosk/kiosk-background-clear.png`.

> Use case: precise-object-edit. Asset type: clean background plate for a layered game UI. Edit target: the supplied image. Remove the remaining blue pixel moon in the upper right, the crystal formation AND its raised stone pedestal in the lower right, and ALL foreground crystals and their stone bases in BOTH bottom corners. Fill the moon area with matching empty dark blue sky. Fill the removed foreground/pedestal areas with a continuous version of the existing dark cyan and black checkerboard floor in the same perspective, texture, and lighting. Keep the entire central neon gateway, its placement, proportions and appearance unchanged. Keep the empty sky, lighting, floor horizon, viewpoint, canvas framing and aspect ratio unchanged. Do not add any crystals, islands, moons, stars, text or new objects. The output should be the same scene with ONLY the central gateway, empty dark sky and continuous tiled ground. The original crystal pixels will be drawn separately by the application; do not redesign them. Preserve image dimensions 1672x941 if possible.
