"""Stationary lava artwork with gently varying incandescent color."""

import logging
import math

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene


LOG = logging.getLogger("oh-no-parent-control")
# Limit color selection to the portal, in fractions of the source artwork.
PORTAL_BOUNDS = (480 / 1672, 36 / 941, 1090 / 1672, 906 / 941)


def heat_level(elapsed):
    """Smooth, overlapping heat pulses, independent of frame rate and position.

    Time changes only color intensity. There is deliberately no spatial phase
    or moving noise that could make highlights appear to travel along a band.
    """
    return (
        0.5
        + 0.27 * math.sin(elapsed * 1.7)
        + 0.16 * math.sin(elapsed * 2.93 + 1.1)
        + 0.07 * math.sin(elapsed * 0.71 + 2.4)
    )


class LavaBands:
    """Cache two color treatments of exactly the same original lava pixels.

    Both treatments retain the source texture detail and a shared, immutable
    alpha mask. Drawing changes only their opacity; the artwork's cover bounds
    are the only transform, and are identical to the background's bounds.
    """

    def __init__(self, original):
        self._cool = self._hot = None
        if original is None:
            return

        width, height = original.get_width(), original.get_height()
        left, top, right, bottom = (
            round(fraction * dimension)
            for fraction, dimension in zip(PORTAL_BOUNDS, (width, height) * 2)
        )
        crop_width, crop_height = right - left, bottom - top
        self._bounds = (left / width, top / height,
                        crop_width / width, crop_height / height)
        downloader = Gdk.TextureDownloader.new(original)
        downloader.set_format(Gdk.MemoryFormat.R8G8B8A8)
        pixel_bytes, stride = downloader.download_bytes()
        pixels = pixel_bytes.get_data()
        cool = bytearray(crop_width * crop_height * 4)
        hot = bytearray(len(cool))
        selected = 0
        for y in range(top, bottom):
            for x in range(left, right):
                source = y * stride + x * 4
                red, green, blue, alpha = pixels[source:source + 4]
                # Orange/yellow emission has both red and green above blue.
                # Soft chroma thresholds retain antialiasing and exclude the
                # violet metal, cyan lighting, opening, and nearby crystals.
                warmth = min(1.0, max(0.0, (red - blue - 45) / 100))
                warmth *= min(1.0, max(0.0, (green - blue - 8) / 60))
                warmth *= min(1.0, max(0.0, (red - 110) / 100))
                opacity = round(alpha * warmth)
                if not opacity:
                    continue
                target = ((y - top) * crop_width + x - left) * 4
                cool[target:target + 4] = bytes((
                    round(red * 0.85), round(green * 0.55),
                    round(blue * 0.5), opacity,
                ))
                hot[target:target + 4] = bytes((
                    min(255, round(red * 1.08 + 12)),
                    min(255, round(green * 1.4 + 28)),
                    min(255, round(blue * 0.8 + 5)), opacity,
                ))
                selected += 1

        if not selected:
            LOG.warning("gateway lava mask contains no warm pixels; heat disabled")
            return
        self._cool, self._hot = (
            Gdk.MemoryTexture.new(
                crop_width, crop_height, Gdk.MemoryFormat.R8G8B8A8,
                GLib.Bytes.new(bytes(treatment)), crop_width * 4,
            )
            for treatment in (cool, hot)
        )
        LOG.debug(
            "gateway lava heat configured pixels=%d animation=color-only "
            "mask=fixed geometry=fixed", selected,
        )

    def draw(self, snapshot, artwork, elapsed):
        if self._hot is None:
            return
        x, y, width, height = artwork
        left, top, crop_width, crop_height = self._bounds
        bounds = Graphene.Rect().init(
            x + left * width, y + top * height,
            crop_width * width, crop_height * height,
        )
        heat = heat_level(elapsed)
        for texture, opacity in (
            (self._cool, 0.65 * (1 - heat)),
            (self._hot, 0.85 * heat),
        ):
            snapshot.push_opacity(opacity)
            snapshot.append_texture(texture, bounds)
            snapshot.pop()
