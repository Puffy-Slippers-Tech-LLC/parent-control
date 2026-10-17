"""Stationary lava artwork with gently varying incandescent color."""

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
import math
from pathlib import Path
import struct
import zlib

from .lava_artwork import PORTAL_BOUNDS, crop, load, treatments

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene


LOG = get_logger("kiosk-lava")


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

    def __init__(self, original, *, cached=False):
        self._cool = self._hot = None
        if original is None:
            return

        width, height = original.get_width(), original.get_height()
        left, top, right, bottom = crop(width, height)
        crop_width, crop_height = right - left, bottom - top
        self._bounds = (left / width, top / height,
                        crop_width / width, crop_height / height)
        prepared = None
        if cached:
            try:
                prepared = load(Path(__file__).with_name('lava-heat.bin'),
                                Path(__file__).with_name('kiosk-background-still.png'),
                                width, height)
            except (OSError, ValueError, struct.error, zlib.error):
                # Checkout previews and edited artwork retain the exact original
                # calculation; a stale or damaged cache never changes the scene.
                pass
        LOG.info('kiosk-lava.cache', cached=prepared is not None)
        if prepared is None:
            downloader = Gdk.TextureDownloader.new(original)
            downloader.set_format(Gdk.MemoryFormat.R8G8B8A8)
            pixel_bytes, stride = downloader.download_bytes()
            prepared = treatments(width, height, pixel_bytes.get_data(), stride)
        cool, hot, selected = prepared

        if not selected:
            LOG.warning("kiosk-lava.001")
            return
        self._cool, self._hot = (
            Gdk.MemoryTexture.new(
                crop_width, crop_height, Gdk.MemoryFormat.R8G8B8A8,
                GLib.Bytes.new(bytes(treatment)), crop_width * 4,
            )
            for treatment in (cool, hot)
        )
        LOG.debug("kiosk-lava.002", pixels=selected)

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
