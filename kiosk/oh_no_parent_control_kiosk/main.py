"""Libadwaita application for the GNOME Kiosk request station."""

from __future__ import annotations

import argparse
import cairo
import logging
import json
import math
import os
import random
import sys
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gsk, Gst, Gtk

from common.oh_no_parent_control_ui.about import AboutDialog, app_name, open_help
from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.test_identities import preview_users

from .model import RequestState, public_error
from .request_content import RequestContent
from .selection_store import SelectionStore
from .chrome import (
    ABOUT, BOARD_CHAIN_ANCHOR_END_INSET, BOARD_CHAIN_ANCHOR_SIDE_INSET, HELP,
    MENU, SPEAKER, SPEAKER_MUTED, ArmoredButton, ArmoredMenuButton, HudIconFrame,
    HudMenuBoard, HudMenuStem, MetalBoard, PixelIcon,
)

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
# An authorization prompt remains open until the administrator responds.
# G_MAXINT is GIO's supported no-timeout value.
REQUEST_TIMEOUT_MS = GLib.MAXINT
# Keep the confirmation visible briefly before returning to GDM or
# closing the child overlay.  Fade the soundtrack over the same interval
# so dismissal does not cut the music off.
SUCCESS_LOGOUT_DELAY_MS = 3_000
SUCCESS_COUNTDOWN_SECONDS = SUCCESS_LOGOUT_DELAY_MS // 1_000
MUSIC_FADE_TICK_MS = 50
# Keep the soundtrack comfortably behind form interaction and let a live bolt
# read as a deliberate electrical event rather than background texture.
BACKGROUND_MUSIC_VOLUME = 0.18
LIGHTNING_SIZZLE_VOLUME = 0.70
CHILD_SUCCESS_TITLE = "Time granted"
CHILD_SUCCESS_COPY = "Time granted, Close"
GATEWAY_EFFECT_FRAME_MS = 33
# The form is centered in the window while the gateway in the artwork is
# slightly left of the image centre.  Shift the composed artwork just enough
# to centre the form within the gateway at every resolution.
GATEWAY_CENTERING_OFFSET = 0.03125
# Native dimensions and measured corners of the gateway opening.  These points
# sit on the innermost purple edge, rather than on the outer cyan frame. Keeping
# them in source-image space lets the anchors follow the same responsive cover
# scaling and crop as the painted texture.
GATEWAY_ARTWORK_WIDTH = 3_840
GATEWAY_ARTWORK_HEIGHT = 2_160
# The six intended formations in the supplied artwork: four on the left and
# two on the right. Each point is the visible tip of a crystal, in source-image
# fractions, so an ejection visibly starts at its crystal rather than in the
# surrounding cluster. These source-image coordinates also survive cover crop.
CRYSTAL_LIGHTNING_TIPS = (
    (0.154, 0.096),  # floating upper-left formation
    (0.099, 0.342),  # left pedestal formation
    (0.178, 0.618),  # lower-left pedestal formation
    (0.077, 0.873),  # foreground bottom-left formation
    (0.783, 0.383),  # right pedestal formation
    (0.827, 0.644),  # lower-right formation
)
GATEWAY_INNER_CORNERS = (
    (1_374 / GATEWAY_ARTWORK_WIDTH, 347 / GATEWAY_ARTWORK_HEIGHT),
    (2_276 / GATEWAY_ARTWORK_WIDTH, 405 / GATEWAY_ARTWORK_HEIGHT),
    (2_276 / GATEWAY_ARTWORK_WIDTH, 1_780 / GATEWAY_ARTWORK_HEIGHT),
    (1_374 / GATEWAY_ARTWORK_WIDTH, 1_837 / GATEWAY_ARTWORK_HEIGHT),
)
# Project the complete form as the flat surface mounted inside the gateway.
# The gateway's horizon crosses the middle of the form, so its upper edges
# descend to the right while its lower edges rise to the right.
GATEWAY_FORM_YAW_DEGREES = 10.0
GATEWAY_FORM_PERSPECTIVE_DEPTH = 1_200.0
# The visible gateway opening is slightly right of the overlay's allocation
# centre. Keep the mounted form centred in that opening at every resolution.
GATEWAY_FORM_CENTERING_OFFSET = 0.019
PREVIEW_DEFAULT_WIDTH = 1918
PREVIEW_DEFAULT_HEIGHT = 1443
PREVIEW_USERS = preview_users("child")
PREVIEW_APPROVERS = preview_users("parent")
PREVIEW_PREFERENCES = {
    1001: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1002: {
        "parent_control_enabled": False,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1003: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1004: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
    1005: {
        "parent_control_enabled": True,
        "request": {
            "last_selected_duration": "1800",
            "last_custom_minutes": 30,
            "allow_soft_blocked_apps": False,
        },
    },
}
LOG = logging.getLogger("oh-no-parent-control")


def _gateway_artwork_geometry(width, height):
    """Return the gateway artwork's cover-scaled bounds in widget space."""
    scale = max(
        width / GATEWAY_ARTWORK_WIDTH,
        height / GATEWAY_ARTWORK_HEIGHT,
    )
    rendered_width = GATEWAY_ARTWORK_WIDTH * scale
    rendered_height = GATEWAY_ARTWORK_HEIGHT * scale
    return (
        (width - rendered_width) / 2
        + rendered_width * GATEWAY_CENTERING_OFFSET,
        (height - rendered_height) / 2,
        rendered_width,
        rendered_height,
    )


def _gateway_inner_corners(width, height):
    """Map the artwork's four inner gateway corners into widget space."""
    image_x, image_y, rendered_width, rendered_height = (
        _gateway_artwork_geometry(width, height)
    )
    return tuple(
        (
            image_x + normalized_x * rendered_width,
            image_y + normalized_y * rendered_height,
        )
        for normalized_x, normalized_y in GATEWAY_INNER_CORNERS
    )


def _centroid(points):
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
    )


def _unit_vector(origin, target):
    vector_x = target[0] - origin[0]
    vector_y = target[1] - origin[1]
    length = math.hypot(vector_x, vector_y)
    if length < 1e-9:
        return (0.0, 0.0)
    return (vector_x / length, vector_y / length)


def _convex_hull(points):
    """Return the counterclockwise convex hull of 2D points."""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return tuple(unique)

    def cross(origin, first, second):
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    def half(sequence):
        hull = []
        for point in sequence:
            while len(hull) >= 2 and cross(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
        return hull

    lower = half(unique)
    upper = half(reversed(unique))
    return tuple(lower[:-1] + upper[:-1])


class BrokerLogHandler(logging.Handler):
    """Forward front-end records to the broker-owned daily log."""

    def __init__(self, component="kiosk"):
        super().__init__()
        self._component = component
        self._connection = None

    def emit(self, record):
        try:
            if self._connection is None:
                self._connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self._connection.call(
                BUS_NAME, OBJECT_PATH, INTERFACE, "LogEvent",
                GLib.Variant("(sss)", (self._component, record.levelname, self.format(record))),
                GLib.VariantType.new("()"), Gio.DBusCallFlags.NONE, 5_000, None, None,
            )
        except Exception:
            self._connection = None


class BackgroundMusic:
    """Keep the kiosk soundtrack playing for the lifetime of its window."""

    def __init__(self, soundtrack=None):
        Gst.init(None)
        self._player = Gst.ElementFactory.make("playbin")
        if self._player is None:
            raise RuntimeError("GStreamer playbin is unavailable")
        track = Gio.File.new_for_path(
            str(soundtrack or Path(__file__).with_name("Gearbox_Waltz.mp3")),
        )
        self._player.set_property("uri", track.get_uri())
        self._bus = self._player.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect("message::eos", self._restart)
        self._bus.connect("message::error", self._error)
        self._fade_source_id = None
        self._nominal_volume = BACKGROUND_MUSIC_VOLUME

    def start(self):
        self._player.set_property("volume", self._nominal_volume)
        self._player.set_state(Gst.State.PLAYING)

    def set_muted(self, muted):
        """Mute or restore the soundtrack without interrupting its loop."""
        self._player.set_property("mute", muted)

    def fade_out(self, duration_ms):
        """Lower volume to silence over duration_ms, then leave it at zero."""
        self.cancel_fade(restore=False)
        if self._player.get_property("mute"):
            self._player.set_property("volume", 0.0)
            return
        start_volume = self._player.get_property("volume")
        started_us = GLib.get_monotonic_time()
        duration_us = max(1, duration_ms) * 1_000

        def tick():
            elapsed_us = GLib.get_monotonic_time() - started_us
            if elapsed_us >= duration_us:
                self._player.set_property("volume", 0.0)
                self._fade_source_id = None
                return GLib.SOURCE_REMOVE
            remaining = 1.0 - (elapsed_us / duration_us)
            self._player.set_property("volume", start_volume * remaining)
            return GLib.SOURCE_CONTINUE

        self._fade_source_id = GLib.timeout_add(MUSIC_FADE_TICK_MS, tick)

    def cancel_fade(self, restore=True):
        """Stop an in-progress fade and optionally restore playback volume."""
        if self._fade_source_id is not None:
            GLib.source_remove(self._fade_source_id)
            self._fade_source_id = None
        if restore:
            self._player.set_property("volume", self._nominal_volume)

    def close(self):
        self.cancel_fade(restore=False)
        self._bus.remove_signal_watch()
        self._player.set_state(Gst.State.NULL)

    def _restart(self, _bus, _message):
        """Seek to the start after each completed track."""
        self._player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            0,
        )
        self._player.set_state(Gst.State.PLAYING)

    @staticmethod
    def _error(_bus, _message):
        LOG.warning("kiosk background music playback failed")


class LightningSizzle:
    """Brief, quiet electrical noise mixed independently with the soundtrack."""

    def __init__(self):
        self._pipeline = None
        self._gain = None
        self._stop_source_id = None
        self._fade_source_id = None
        self._active_bolts = []
        self._sizzle_level = 0.0
        self._dismissal_level = 1.0
        self._muted = False
        try:
            self._pipeline = Gst.parse_launch(
                "audiotestsrc is-live=true wave=white-noise ! "
                "audioconvert ! audioresample ! "
                "volume name=lightning_sizzle_gain ! autoaudiosink",
            )
            self._gain = self._pipeline.get_by_name("lightning_sizzle_gain")
            self._apply_volume()
        except GLib.Error as error:
            LOG.warning(
                "lightning sizzle unavailable error_type=%s", type(error).__name__,
            )
            self._pipeline = None

    def _apply_volume(self):
        if self._gain is not None:
            volume = (
                LIGHTNING_SIZZLE_VOLUME
                * self._sizzle_level
                * self._dismissal_level
            )
            self._gain.set_property("volume", 0.0 if self._muted else volume)

    def play(self, duration_seconds, fade_rate):
        """Fade this bolt's sizzle with its matching visual lightning fade."""
        if self._pipeline is None:
            return
        now_us = GLib.get_monotonic_time()
        duration_us = int(max(0.0, duration_seconds) * 1_000_000)
        self._active_bolts.append(
            (now_us + duration_us, duration_us, fade_rate),
        )
        self._pipeline.set_state(Gst.State.PLAYING)
        LOG.debug(
            "lightning sizzle started duration_ms=%d", int(duration_seconds * 1_000),
        )
        if self._stop_source_id is None:
            self._stop_source_id = GLib.timeout_add(MUSIC_FADE_TICK_MS, self._stop_if_idle)

    def _stop_if_idle(self):
        now_us = GLib.get_monotonic_time()
        self._active_bolts = [
            bolt for bolt in self._active_bolts if now_us < bolt[0]
        ]
        if self._active_bolts:
            self._sizzle_level = max(
                ((ends_at_us - now_us) / duration_us) ** fade_rate
                for ends_at_us, duration_us, fade_rate in self._active_bolts
                if duration_us > 0
            )
            self._apply_volume()
            return GLib.SOURCE_CONTINUE
        self._sizzle_level = 0.0
        self._apply_volume()
        self._pipeline.set_state(Gst.State.READY)
        self._stop_source_id = None
        return GLib.SOURCE_REMOVE

    def set_muted(self, muted):
        """Apply the request screen's persisted sound control to the sizzle."""
        self._muted = muted
        self._apply_volume()

    def fade_out(self, duration_ms):
        """Fade the effect with the soundtrack during successful dismissal."""
        self.cancel_fade(restore=False)
        started_us = GLib.get_monotonic_time()
        duration_us = max(1, duration_ms) * 1_000

        def tick():
            elapsed_us = GLib.get_monotonic_time() - started_us
            if elapsed_us >= duration_us:
                self._dismissal_level = 0.0
                self._apply_volume()
                self._fade_source_id = None
                return GLib.SOURCE_REMOVE
            self._dismissal_level = 1 - elapsed_us / duration_us
            self._apply_volume()
            return GLib.SOURCE_CONTINUE

        self._fade_source_id = GLib.timeout_add(MUSIC_FADE_TICK_MS, tick)

    def cancel_fade(self, restore=True):
        if self._fade_source_id is not None:
            GLib.source_remove(self._fade_source_id)
            self._fade_source_id = None
        if restore:
            self._dismissal_level = 1.0
            self._apply_volume()

    def close(self):
        self.cancel_fade(restore=False)
        if self._stop_source_id is not None:
            GLib.source_remove(self._stop_source_id)
            self._stop_source_id = None
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None


class GatewayBackground(Gtk.Widget):
    """Static kiosk artwork with animated energy travelling through its gateway."""

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self._started_at = GLib.get_monotonic_time() / 1_000_000
        self._texture = self._load_texture()
        self._random = random.SystemRandom()
        self._lightning_bolts = []
        self._next_lightning_burst_at = 0.0
        self._lightning_sizzle = None
        self._frame_source_id = GLib.timeout_add(
            GATEWAY_EFFECT_FRAME_MS, self._next_frame,
        )
        self.connect("destroy", self._stop_animation)

    @staticmethod
    def _load_texture():
        try:
            image_file = Gio.File.new_for_path(
                str(Path(__file__).with_name("kiosk-background.jpeg")),
            )
            return Gdk.Texture.new_from_file(image_file)
        except GLib.Error as error:
            LOG.warning("kiosk background unavailable error_type=%s", type(error).__name__)
            return None

    def reload_texture(self):
        """Refresh the preview artwork without rebuilding the window."""
        self._texture = self._load_texture()
        self.queue_draw()

    def _next_frame(self):
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _stop_animation(self, *_args):
        if self._frame_source_id is not None:
            GLib.source_remove(self._frame_source_id)
            self._frame_source_id = None

    def set_lightning_sizzle(self, play_sizzle):
        """Connect bolt starts to the window-owned, muteable audio effect."""
        self._lightning_sizzle = play_sizzle

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        bounds = Graphene.Rect().init(0, 0, width, height)
        snapshot.append_color(
            Gdk.RGBA(red=0.03, green=0.04, blue=0.09, alpha=1.0),
            bounds,
        )
        if self._texture is None or width <= 0 or height <= 0:
            return

        now = GLib.get_monotonic_time() / 1_000_000 - self._started_at
        image_bounds = Graphene.Rect().init(
            *_gateway_artwork_geometry(width, height)
        )
        snapshot.append_texture(self._texture, image_bounds)

        # A low-opacity vignette preserves legibility while allowing the
        # supplied artwork to remain prominent.
        snapshot.append_color(
            Gdk.RGBA(red=0.02, green=0.03, blue=0.09, alpha=0.24),
            bounds,
        )
        self._append_gateway_energy(snapshot, width, height, now)

    def _new_lightning_bolt(self, starts_at):
        """Create one non-repeating bolt from a crystal into the gate."""
        source_x, source_y = self._random.choice(CRYSTAL_LIGHTNING_TIPS)
        return {
            "starts_at": starts_at,
            "duration": self._random.uniform(0.85, 1.35),
            "source_x": source_x,
            "source_y": source_y,
            "target_x": self._random.uniform(0.44, 0.56),
            "target_y": self._random.uniform(0.42, 0.56),
            # Store a unique irregular path with the bolt so it stays stable
            # while it travels, but no two strikes share a zig-zag pattern.
            "path_offsets": self._new_winding_offsets(),
            "detail_offsets": self._new_secondary_offsets(),
            "winding": self._random.uniform(0.08, 0.16),
            "jaggedness": self._random.uniform(8, 24),
            # A few intense strikes create the bright, high-energy flashes
            # while dimmer ones keep the scene from looking uniformly lit.
            "brightness": self._random.uniform(0.28, 2.4),
            "fade_rate": self._random.uniform(0.68, 1.35),
            # A broad range keeps the scene from looking like duplicated
            # effects: some bolts are hairline flashes while others dominate
            # the background with a heavy strike.
            "thickness": self._random.uniform(0.22, 6.6),
            "branches": tuple(
                (
                    self._random.uniform(0.16, 0.82),
                    self._random.uniform(0.06, 0.18),
                    self._random.choice((-1, 1)),
                    self._random.uniform(-1.0, 1.0),
                    # Forks do not inherit identical brightness or decay.
                    # This keeps a single strike from reading as a copied
                    # bundle of lines as it approaches the gateway.
                    self._random.uniform(0.20, 2.4),
                    self._random.uniform(0.45, 1.7),
                    self._random.uniform(0.35, 1.25),
                )
                # A strike may remain unbranched, or split into up to four
                # independently lit offshoots.
                for _branch in range(self._random.randint(0, 4))
            ),
        }

    def _launch_lightning_burst(self, elapsed):
        """Queue a staggered, randomly sized set of crystal ejections."""
        ejection_count = self._random.randint(1, 4)
        starts_at = elapsed + self._random.uniform(0.06, 0.28)
        for _ejection in range(ejection_count):
            self._lightning_bolts.append(self._new_lightning_bolt(starts_at))
            # Each ejection gets its own moment; later bolts can still overlap
            # a fading earlier bolt without appearing simultaneously.
            starts_at += self._random.uniform(0.12, 0.38)
        self._next_lightning_burst_at = starts_at + self._random.uniform(0.45, 1.25)

    def _new_winding_offsets(self):
        """Build gentle, irregular turns that resolve at the gateway."""
        anchors = [0.0]
        for _anchor in range(3):
            anchors.append(self._random.uniform(-0.85, 0.85))
        anchors.append(0.0)
        return self._smooth_offsets(anchors)

    def _new_secondary_offsets(self):
        """Build smaller smooth bends that flicker within the broad route."""
        anchors = [0.0]
        for _anchor in range(8):
            anchors.append(self._random.uniform(-0.9, 0.9))
        anchors.append(0.0)
        return self._smooth_offsets(anchors)

    @staticmethod
    def _smooth_offsets(anchors):
        offsets = []
        for point in range(22):
            position = point / 21 * (len(anchors) - 1)
            anchor_index = min(int(position), len(anchors) - 2)
            fraction = position - anchor_index
            # Cosine interpolation gives each broad turn a smooth entry and
            # exit, rather than connecting random points with sharp corners.
            smooth_fraction = (1 - math.cos(math.pi * fraction)) / 2
            offsets.append(
                anchors[anchor_index] * (1 - smooth_fraction)
                + anchors[anchor_index + 1] * smooth_fraction
            )
        return tuple(offsets)

    def _append_gateway_energy(self, snapshot, width, height, elapsed):
        """Draw bright, randomly sourced lightning moving into the gateway."""
        bounds = Graphene.Rect().init(0, 0, width, height)
        context = snapshot.append_cairo(bounds)

        self._lightning_bolts = [
            bolt for bolt in self._lightning_bolts
            if elapsed < bolt["starts_at"] + bolt["duration"]
        ]
        if elapsed >= self._next_lightning_burst_at:
            self._launch_lightning_burst(elapsed)

        image_x, image_y, image_width, image_height = _gateway_artwork_geometry(
            width, height,
        )

        for bolt in self._lightning_bolts:
            progress = (elapsed - bolt["starts_at"]) / bolt["duration"]
            if not 0 <= progress <= 1:
                continue
            if not bolt.get("sizzle_started"):
                bolt["sizzle_started"] = True
                if self._lightning_sizzle is not None:
                    self._lightning_sizzle(bolt["duration"], bolt["fade_rate"])
            source_x = image_x + bolt["source_x"] * image_width
            source_y = image_y + bolt["source_y"] * image_height
            target_x, target_y = bolt["target_x"] * width, bolt["target_y"] * height
            vector_x, vector_y = target_x - source_x, target_y - source_y
            vector_length = math.hypot(vector_x, vector_y)
            perpendicular_x, perpendicular_y = -vector_y / vector_length, vector_x / vector_length
            # A lightning flash is brightest at its origin, then loses energy
            # while travelling into the gateway instead of staying uniformly
            # bright for its whole journey.
            opacity = min(
                1.0,
                0.98 * bolt["brightness"] * (1 - progress) ** bolt["fade_rate"],
            )
            # Energy collapses into a thin line near the gateway, matching
            # the rapid fade rather than retaining a broad neon stroke.
            thickness = bolt["thickness"] * (1 - progress) ** 1.35
            bend_scale = vector_length * bolt["winding"]

            points = []
            for step, (path_offset, detail_offset) in enumerate(zip(
                bolt["path_offsets"], bolt["detail_offsets"],
            )):
                point_progress = progress * step / (len(bolt["path_offsets"]) - 1)
                jitter = (
                    bend_scale * path_offset
                    + bolt["jaggedness"] * detail_offset
                )
                points.append((
                    source_x + vector_x * point_progress + perpendicular_x * jitter,
                    source_y + vector_y * point_progress + perpendicular_y * jitter,
                ))

            context.move_to(*points[0])
            for point in points[1:]:
                context.line_to(*point)
            context.set_source_rgba(0.29, 0.08, 1.0, opacity * 0.62)
            context.set_line_width(20 * thickness)
            context.stroke_preserve()
            context.set_source_rgba(0.60, 0.40, 1.0, opacity * 0.88)
            context.set_line_width(8 * thickness)
            context.stroke_preserve()
            context.set_source_rgba(0.98, 0.96, 1.0, opacity)
            context.set_line_width(2.4 * thickness)
            context.stroke()

            # Each optional fork carries individual brightness and fade
            # values, so it fades naturally instead of mirroring the trunk.
            for (
                branch_at,
                branch_length,
                branch_side,
                branch_bend,
                branch_lightness,
                branch_fade_rate,
                branch_taper_rate,
            ) in bolt["branches"]:
                if branch_at >= progress:
                    continue
                branch_x = source_x + vector_x * branch_at
                branch_y = source_y + vector_y * branch_at
                path_position = branch_at * (len(bolt["path_offsets"]) - 1)
                path_index = int(path_position)
                path_fraction = path_position - path_index
                path_offset = (
                    bolt["path_offsets"][path_index] * (1 - path_fraction)
                    + bolt["path_offsets"][path_index + 1] * path_fraction
                )
                detail_offset = (
                    bolt["detail_offsets"][path_index] * (1 - path_fraction)
                    + bolt["detail_offsets"][path_index + 1] * path_fraction
                )
                jitter = bend_scale * path_offset + bolt["jaggedness"] * detail_offset
                branch_x += perpendicular_x * jitter
                branch_y += perpendicular_y * jitter
                end_x = branch_x - vector_x * branch_length
                end_y = branch_y - vector_y * branch_length
                end_x += perpendicular_x * vector_length * branch_length * 0.85 * branch_side
                end_y += perpendicular_y * vector_length * branch_length * 0.85 * branch_side
                context.move_to(branch_x, branch_y)
                context.line_to(
                    (branch_x + end_x) / 2
                    + perpendicular_x * vector_length * branch_length * branch_bend * 0.45,
                    (branch_y + end_y) / 2
                    + perpendicular_y * vector_length * branch_length * branch_bend * 0.45,
                )
                context.line_to(end_x, end_y)
                branch_opacity = (
                    0.98
                    * branch_lightness
                    * (1 - progress) ** branch_fade_rate
                )
                # Forks lose physical width as well as light.  Their taper
                # rates are independent, so some disappear as hairlines
                # while others keep a thicker glow a little longer.
                branch_thickness = (
                    thickness * (1 - progress) ** branch_taper_rate
                )
                context.set_source_rgba(
                    0.38,
                    0.12,
                    1.0,
                    branch_opacity * 0.44,
                )
                context.set_line_width(9 * branch_thickness)
                context.stroke_preserve()
                context.set_source_rgba(
                    0.94,
                    0.88,
                    1.0,
                    branch_opacity * 0.84,
                )
                context.set_line_width(1.7 * branch_thickness)
                context.stroke()


def _gateway_form_scale(width, height, form_width, form_height):
    """Keep the form's design size relative to the gateway at every resolution.

    The board is authored against the preview window. Cover-scaling the
    artwork already tracks monitor size, so the form uses that same ratio.
    A further fit clamp keeps the yawed board inside a smaller allocation
    instead of clipping its natural height.
    """
    _image_x, _image_y, rendered_width, _rendered_height = (
        _gateway_artwork_geometry(width, height)
    )
    preview_cover = max(
        PREVIEW_DEFAULT_WIDTH / GATEWAY_ARTWORK_WIDTH,
        PREVIEW_DEFAULT_HEIGHT / GATEWAY_ARTWORK_HEIGHT,
    )
    window_cover = (
        rendered_width / GATEWAY_ARTWORK_WIDTH if GATEWAY_ARTWORK_WIDTH else 1.0
    )
    design_scale = window_cover / preview_cover if preview_cover else 1.0
    if form_width <= 0 or form_height <= 0:
        return design_scale
    fit = min(width / form_width, height / form_height)
    return min(design_scale, fit)


def _gateway_form_projection(width, height, scale=1.0):
    """Return the gateway's perspective transform around the form's centre."""
    return (
        Gsk.Transform.new()
        .translate(Graphene.Point().init(width / 2, height / 2))
        .perspective(GATEWAY_FORM_PERSPECTIVE_DEPTH * scale)
        .rotate_3d(
            GATEWAY_FORM_YAW_DEGREES,
            Graphene.Vec3().init(0, 1, 0),
        )
        .scale(scale, scale)
        .translate(Graphene.Point().init(-width / 2, -height / 2))
    )


class GatewayAlignedRequest(Gtk.Widget):
    """Container that mounts the complete request form in the gateway plane."""

    def __init__(self, child):
        super().__init__(hexpand=True, vexpand=True)
        self._child = child
        self._form_corners = ()
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        return self._child.measure(orientation, for_size)

    def do_size_allocate(self, width, height, baseline):
        _minimum_width, natural_width, _minimum_baseline, _natural_baseline = (
            self._child.measure(Gtk.Orientation.HORIZONTAL, -1)
        )
        child_width = max(1, natural_width)
        _minimum_height, natural_height, _minimum_baseline, _natural_baseline = (
            self._child.measure(Gtk.Orientation.VERTICAL, child_width)
        )
        child_height = max(1, natural_height)
        form_scale = _gateway_form_scale(
            width, height, child_width, child_height,
        )

        projection = _gateway_form_projection(
            child_width, child_height, form_scale,
        )
        projected_bounds = projection.transform_bounds(
            Graphene.Rect().init(0, 0, child_width, child_height),
        )
        placement = Graphene.Point().init(
            (width - projected_bounds.get_width()) / 2
            - projected_bounds.get_x()
            + width * GATEWAY_FORM_CENTERING_OFFSET,
            (height - projected_bounds.get_height()) / 2 - projected_bounds.get_y(),
        )
        transform = Gsk.Transform.new().translate(placement).transform(projection)
        # Use the complete allocation transform for the attachment points and
        # terminate each chain at a visible lug on the vertical rail. Attaching
        # to the mathematical outer vertices leaves a hollow ring wrapped
        # around the board and reads as floating instead of mechanically
        # secured.
        side = BOARD_CHAIN_ANCHOR_SIDE_INSET
        end = BOARD_CHAIN_ANCHOR_END_INSET
        self._form_corners = tuple(
            (projected.x, projected.y)
            for projected in (
                transform.transform_point(Graphene.Point().init(x, y))
                for x, y in (
                    (side, end),
                    (child_width - side, end),
                    (child_width - side, child_height - end),
                    (side, child_height - end),
                )
            )
        )
        self._child.allocate(child_width, child_height, baseline, transform)

    def do_snapshot(self, snapshot):
        self._append_gateway_chains(snapshot)
        self.snapshot_child(self._child, snapshot)

    def _append_gateway_chains(self, snapshot):
        """Draw four block-built chains behind the gateway-mounted form."""
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0 or len(self._form_corners) != 4:
            return

        bounds = Graphene.Rect().init(0, 0, width, height)
        context = snapshot.append_cairo(bounds)
        link_length = max(18.0, min(42.0, min(width, height) * 0.03))
        gateway_corners = _gateway_inner_corners(width, height)

        # The gateway artwork is a single background texture, so it cannot
        # naturally occlude overlay content. Clip to the convex hull of the
        # inner opening and the live form lugs: terminal links still disappear
        # beneath the frame, while a board taller than the opening keeps a
        # visible run of chain out to its corners instead of being cropped at
        # the gateway's top and bottom edges.
        clip_polygon = _convex_hull((*gateway_corners, *self._form_corners))
        context.save()
        if len(clip_polygon) >= 3:
            context.move_to(*clip_polygon[0])
            for corner in clip_polygon[1:]:
                context.line_to(*corner)
            context.close_path()
            context.clip()

        opening_center = _centroid(gateway_corners)
        form_center = _centroid(self._form_corners)
        for gateway_corner, form_corner in zip(
            gateway_corners, self._form_corners,
        ):
            self._draw_minecraft_chain(
                context, gateway_corner, form_corner, link_length,
                start_extend=_unit_vector(opening_center, gateway_corner),
                end_extend=_unit_vector(form_corner, form_center),
            )
        context.restore()

    @classmethod
    def _draw_minecraft_chain(
        cls, context, start, end, link_length, start_extend=None, end_extend=None,
    ):
        """Draw interlocking, angular links between two attachment points."""
        vector_x = end[0] - start[0]
        vector_y = end[1] - start[1]
        distance = math.hypot(vector_x, vector_y)
        if distance < 1:
            return

        # Bury the gateway terminal beneath the inner frame, and seat the form
        # terminal under the board bevel.  Those extensions follow the opening
        # and the board, not the chain direction, so a form that sticks out of
        # the gateway still meets a chain at its lug instead of stretching the
        # inset the wrong way.
        unit_x = vector_x / distance
        unit_y = vector_y / distance
        gateway_inset = max(12.0, min(24.0, link_length * 0.68))
        form_overlap = max(18.0, min(38.0, link_length * 0.90))
        if start_extend is None:
            start_extend = (-unit_x, -unit_y)
        if end_extend is None:
            end_extend = (unit_x, unit_y)
        start = (
            start[0] + start_extend[0] * gateway_inset,
            start[1] + start_extend[1] * gateway_inset,
        )
        end = (
            end[0] + end_extend[0] * form_overlap,
            end[1] + end_extend[1] * form_overlap,
        )
        vector_x = end[0] - start[0]
        vector_y = end[1] - start[1]
        distance = math.hypot(vector_x, vector_y)
        link_length = min(link_length, distance)

        # Gravity pulls the middle of each chain downward while preserving its
        # exact endpoints. Sample the quadratic curve so links remain evenly
        # spaced by travelled distance rather than by its parameter value.
        sag = min(link_length * 1.25, distance * 0.13)
        curve_samples = cls._chain_curve_samples(start, end, sag)
        curve_length = curve_samples[-1][0]
        chain_span = max(0.0, curve_length - link_length)
        preferred_spacing = link_length * 0.58
        link_count = max(1, math.ceil(chain_span / preferred_spacing) + 1)

        for link_index in range(link_count):
            travelled = (
                curve_length / 2 if link_count == 1
                else link_length / 2
                + chain_span * link_index / (link_count - 1)
            )
            center_x, center_y, angle = cls._chain_curve_position(
                curve_samples, travelled,
            )
            # Alternating broad and edge-on rings mimic Minecraft's linked,
            # block-built chain silhouette rather than a dashed cable.
            edge_on = link_index % 2 == 1
            # The terminal ring is the visible attachment hardware.  Keep it
            # broad even when the alternating sequence would make it edge-on,
            # so it meets the form with a continuous, substantial silhouette.
            if link_index == link_count - 1:
                edge_on = False
            cls._draw_angular_chain_link(
                context, center_x, center_y, angle, link_length, edge_on,
            )

    @staticmethod
    def _chain_curve_samples(start, end, sag, sample_count=32):
        """Return cumulative-distance samples of a gravity-sagged chain."""
        control_x = (start[0] + end[0]) / 2
        control_y = (start[1] + end[1]) / 2 + sag * 2
        samples = []
        previous_x = previous_y = None
        travelled = 0.0
        for sample_index in range(sample_count + 1):
            progress = sample_index / sample_count
            inverse = 1 - progress
            point_x = (
                inverse * inverse * start[0]
                + 2 * inverse * progress * control_x
                + progress * progress * end[0]
            )
            point_y = (
                inverse * inverse * start[1]
                + 2 * inverse * progress * control_y
                + progress * progress * end[1]
            )
            tangent_x = (
                2 * inverse * (control_x - start[0])
                + 2 * progress * (end[0] - control_x)
            )
            tangent_y = (
                2 * inverse * (control_y - start[1])
                + 2 * progress * (end[1] - control_y)
            )
            if previous_x is not None:
                travelled += math.hypot(
                    point_x - previous_x, point_y - previous_y,
                )
            samples.append(
                (travelled, point_x, point_y, math.atan2(tangent_y, tangent_x)),
            )
            previous_x, previous_y = point_x, point_y
        return samples

    @staticmethod
    def _chain_curve_position(samples, target_distance):
        """Interpolate a point and tangent angle at an arc distance."""
        for previous, current in zip(samples, samples[1:]):
            if target_distance > current[0]:
                continue
            segment_length = current[0] - previous[0]
            fraction = (
                0.0 if segment_length <= 0
                else (target_distance - previous[0]) / segment_length
            )
            return (
                previous[1] + (current[1] - previous[1]) * fraction,
                previous[2] + (current[2] - previous[2]) * fraction,
                previous[3] + (current[3] - previous[3]) * fraction,
            )
        return samples[-1][1:]

    @classmethod
    def _draw_angular_chain_link(
        cls, context, center_x, center_y, angle, link_length, edge_on,
    ):
        """Paint one hollow, faceted metal link with a restrained portal glow."""
        half_length = link_length / 2
        half_width = link_length * (0.17 if edge_on else 0.34)
        metal_width = max(3.0, link_length * 0.13)
        inner_half_length = max(half_length * 0.58, half_length - metal_width * 1.7)
        inner_half_width = max(1.0, half_width - metal_width)

        context.save()
        context.translate(center_x, center_y)
        context.rotate(angle)
        context.set_line_join(cairo.LineJoin.MITER)
        context.set_line_cap(cairo.LineCap.BUTT)

        cls._append_angular_link_path(context, half_length, half_width)
        context.set_source_rgba(0.48, 0.16, 0.96, 0.30)
        context.set_line_width(max(5.0, metal_width * 2.35))
        context.stroke()

        cls._append_angular_link_path(context, half_length, half_width)
        cls._append_angular_link_path(
            context, inner_half_length, inner_half_width,
        )
        context.set_fill_rule(cairo.FillRule.EVEN_ODD)
        context.set_source_rgba(0.44, 0.22, 0.68, 1.0)
        context.fill()

        cls._append_angular_link_path(context, half_length, half_width)
        cls._append_angular_link_path(
            context, inner_half_length, inner_half_width,
        )
        context.set_source_rgba(0.06, 0.025, 0.13, 0.96)
        context.set_line_width(max(1.4, metal_width * 0.38))
        context.stroke()

        # A single cool edge catches the gateway light without turning the
        # chain into another lightning effect.
        bevel = min(half_width * 0.62, half_length * 0.16)
        context.move_to(-half_length + bevel, -half_width)
        context.line_to(half_length - bevel, -half_width)
        context.set_source_rgba(
            0.40, 0.98, 0.96, 0.62 if edge_on else 0.86,
        )
        context.set_line_width(max(1.2, metal_width * 0.40))
        context.stroke()
        context.restore()

    @staticmethod
    def _append_angular_link_path(context, half_length, half_width):
        """Append a closed octagonal path for a pixel-art chain ring."""
        bevel = min(half_width * 0.62, half_length * 0.16)
        context.move_to(-half_length + bevel, -half_width)
        context.line_to(half_length - bevel, -half_width)
        context.line_to(half_length, -half_width + bevel)
        context.line_to(half_length, half_width - bevel)
        context.line_to(half_length - bevel, half_width)
        context.line_to(-half_length + bevel, half_width)
        context.line_to(-half_length, half_width - bevel)
        context.line_to(-half_length, -half_width + bevel)
        context.close_path()

    def do_dispose(self):
        if self._child is not None:
            self._child.unparent()
            self._child = None
        Gtk.Widget.do_dispose(self)


def configure_logging(preview=False, component="kiosk"):
    """Use local logging for preview; production records belong to the broker."""
    handler = logging.StreamHandler() if preview else BrokerLogHandler(component)
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class RequestWindow(Adw.ApplicationWindow):
    def __init__(self, application, *, preview=False, soundtrack=None,
                 child_overlay=False, broker_connection=None):
        super().__init__(application=application, title=app_name())
        self.add_css_class("oh-no-parent-control-window")
        if child_overlay:
            self.add_css_class("oh-no-parent-control-overlay")
            self.set_decorated(False)
            self.set_modal(True)
        self.set_default_size(
            PREVIEW_DEFAULT_WIDTH if preview else 800,
            PREVIEW_DEFAULT_HEIGHT if preview else 600,
        )
        self._preview = preview
        # The normal application obtains its connection from the system bus.
        # Tests may inject an API-compatible private connection without
        # changing which production request paths the window executes.
        self._interactive_preview = broker_connection is not None
        self._child_overlay = child_overlay
        self._applying_preferences = False
        self._state = RequestState()
        self._success_logout_source_id = None
        self._success_countdown_remaining = None
        self._success_action_label = None
        self._system_bus = (
            broker_connection if broker_connection is not None else
            (None if preview else Gio.bus_get_sync(Gio.BusType.SYSTEM, None))
        )
        self._build()
        self._music = BackgroundMusic(soundtrack)
        self._sizzle = LightningSizzle()
        self._background.set_lightning_sizzle(self._sizzle.play)
        self._music.start()
        if preview and not child_overlay:
            self._apply_mute(True)
        self.connect("destroy", self._on_destroy)
        LOG.info(
            "request station window initialized overlay=%s",
            child_overlay,
        )
        if not preview:
            self.connect("map", lambda *_args: self.fullscreen())
        self._load_users()

    def _on_destroy(self, *_args):
        self._cancel_success_dismiss()
        if self._music is not None:
            self._music.close()
            self._music = None
        if self._sizzle is not None:
            self._sizzle.close()
            self._sizzle = None

    def _build(self):
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self._background = GatewayBackground()
        self._background.add_css_class("oh-no-parent-control-gateway-background")
        self._background.set_can_target(False)
        layout = Gtk.Overlay()
        layout.set_child(self._background)
        layout.add_overlay(self._stack)
        help_popover = Gtk.Popover()
        help_popover.set_has_arrow(False)
        help_popover.set_position(Gtk.PositionType.BOTTOM)
        help_popover.add_css_class("oh-no-parent-control-hud-menu")
        menu_board = HudMenuBoard(orientation=Gtk.Orientation.VERTICAL)
        menu_board.add_css_class("oh-no-parent-control-hud-menu-board")
        menu_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        menu_actions.add_css_class("oh-no-parent-control-hud-menu-actions")
        if self._child_overlay:
            help_item = self._hud_menu_item("HELP", HELP)
            describe_control(
                help_item, "Help",
                "Open the product website in the browser.",
            )
            help_item.connect(
                "clicked",
                lambda *_args: self._activate_help_menu(help_popover, open_help),
            )
            menu_actions.append(help_item)
        about_item = self._hud_menu_item("ABOUT", ABOUT)
        describe_control(
            about_item, "About",
            "Show product name, version, and legal information.",
        )
        about_item.connect(
            "clicked",
            lambda *_args: self._activate_help_menu(help_popover, self._show_about),
        )
        menu_actions.append(about_item)
        menu_board.append(menu_actions)
        self._muted = False
        self._mute_icon = PixelIcon(SPEAKER, display_size=28, label="")
        self._mute_icon.set_halign(Gtk.Align.CENTER)
        self._mute_icon.set_valign(Gtk.Align.CENTER)
        self._mute_button = ArmoredButton(
            armor_kind="hud", tooltip_text="Mute sound",
        )
        describe_control(
            self._mute_button, "Mute request-screen sound",
            "Turn the request-screen soundtrack on or off.",
        )
        self._mute_button.set_child(self._mute_icon)
        self._mute_button.add_css_class("oh-no-parent-control-hud-button")
        self._mute_button.connect("clicked", self._toggle_mute)
        menu_icon = PixelIcon(MENU, display_size=31, label="")
        menu_icon.set_halign(Gtk.Align.CENTER)
        menu_icon.set_valign(Gtk.Align.CENTER)
        menu_button = ArmoredMenuButton(
            armor_kind="hud",
            tooltip_text="Menu",
            always_show_arrow=False,
            popover=help_popover,
        )
        describe_control(
            menu_button, "Request-screen menu",
            "Open help and product information for this request screen.",
        )
        menu_button.set_child(menu_icon)
        menu_button.add_css_class("oh-no-parent-control-hud-button")
        menu_button.add_css_class("oh-no-parent-control-menu-button")
        menu_button.connect("notify::active", self._menu_state_changed)
        popover_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        popover_content.add_css_class("oh-no-parent-control-hud-menu-content")
        popover_content.append(HudMenuStem())
        popover_content.append(menu_board)
        help_popover.set_child(popover_content)
        top_controls = Gtk.Box(
            spacing=18, halign=Gtk.Align.END, valign=Gtk.Align.START,
            margin_top=24, margin_end=24,
        )
        top_controls.append(self._mute_button)
        top_controls.append(menu_button)
        layout.add_overlay(top_controls)
        if self._preview:
            # The production kiosk is fullscreen, but its frameless preview
            # still needs a compositor-supported surface for moving it.
            drag_handle = Gtk.WindowHandle()
            drag_handle.set_child(layout)
            self.set_content(drag_handle)
        else:
            self.set_content(layout)
        self._cancel = self._close_overlay if self._child_overlay else self._logout
        self._request_content = RequestContent(
            self._request_access, self._cancel, self._load_preferences,
            lock_child_selector=self._child_overlay,
            on_values_changed=self._persist_form_values,
            selection_store=(None if self._preview else SelectionStore(
                Path(GLib.get_user_state_dir()) / "oh-no-parent-control" / "request-selections.json",
                child_overlay=self._child_overlay,
            )),
        )
        self._request_surface = GatewayAlignedRequest(self._request_content)
        self._stack.add_named(self._request_surface, "request")

        self._result_view = self._page()
        self._result_title = Gtk.Label(css_classes=["oh-no-parent-control-page-title"])
        self._result_detail = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._result_view.append(self._result_title)
        self._result_view.append(self._result_detail)
        self._result_action = ArmoredButton(
            label="Close" if self._child_overlay else "Return to Login",
            hexpand=True, armor_kind="request",
        )
        describe_control(
            self._result_action, "Request result action",
            "Close the result screen or return to the sign-in screen.",
        )
        self._result_action.add_css_class("oh-no-parent-control-request-button")
        self._result_action.set_margin_start(10)
        self._result_action.set_margin_end(10)
        self._result_action.connect("clicked", self._cancel)
        self._result_view.append(self._result_action)
        escape = Gtk.EventControllerKey()
        escape.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        escape.connect("key-pressed", self._escape_pressed)
        self.add_controller(escape)
        # Keep every outcome, including the post-authorization confirmation,
        # mounted in the gateway plane.  Adding this box directly to the stack
        # would bypass the yaw and perspective used by the request form.
        self._result_surface = GatewayAlignedRequest(self._result_view)
        self._stack.add_named(self._result_surface, "result")
        if self._child_overlay:
            # The gateway yaw can miss Gtk.Button hit-testing on the result
            # board. Close from the untransformed surface as well as the button.
            close_click = Gtk.GestureClick()
            close_click.connect("released", self._close_overlay)
            self._result_surface.add_controller(close_click)

    def _show_about(self, *_args):
        AboutDialog(self, links_enabled=self._child_overlay).present()

    def _menu_state_changed(self, menu_button, _property):
        LOG.info(
            "request-screen menu expanded=%s overlay=%s",
            menu_button.get_active(),
            self._child_overlay,
        )

    @staticmethod
    def _hud_menu_item(label, icon_pixels):
        item = ArmoredButton(hexpand=True, armor_kind="hud-menu-item")
        item.add_css_class("oh-no-parent-control-hud-menu-item")
        content = Gtk.Box(spacing=18, valign=Gtk.Align.CENTER)
        content.append(HudIconFrame(icon_pixels))
        content.append(Gtk.Label(label=label, xalign=0, hexpand=True))
        item.set_child(content)
        return item

    @staticmethod
    def _activate_help_menu(popover, action):
        popover.popdown()
        action()

    def _mute_surface(self):
        return "child" if self._child_overlay else "kiosk"

    def _apply_mute(self, muted):
        self._muted = muted
        self._music.set_muted(muted)
        self._sizzle.set_muted(muted)
        self._mute_icon.set_pixels(SPEAKER_MUTED if muted else SPEAKER)
        self._mute_button.set_tooltip_text("Unmute sound" if muted else "Mute sound")
        if muted:
            self._mute_button.add_css_class("oh-no-parent-control-hud-muted")
        else:
            self._mute_button.remove_css_class("oh-no-parent-control-hud-muted")
        LOG.info("request-screen sound muted=%s overlay=%s", muted, self._child_overlay)

    def _toggle_mute(self, *_args):
        self._apply_mute(not self._muted)
        self._persist_muted(self._muted)

    @staticmethod
    def _page():
        box = MetalBoard(
            orientation=Gtk.Orientation.VERTICAL, spacing=24,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        )
        box.add_css_class("oh-no-parent-control-dialog")
        box.add_css_class("oh-no-parent-control-secondary-page")
        return box

    def _logout(self, *_args):
        self._cancel_success_dismiss()
        if self._preview:
            if self._music is not None:
                self._music.cancel_fade()
            if self._sizzle is not None:
                self._sizzle.cancel_fade()
            self._stack.set_visible_child_name("request")
            return
        # OnSuccess=gnome-session-shutdown.target on the application unit turns
        # this clean exit into a supported kiosk-session logout back to GDM.
        LOG.info("return to login requested")
        self.get_application().quit()

    def _close_overlay(self, *_args):
        self._cancel_success_dismiss()
        LOG.info("child request overlay closed")
        application = self.get_application()
        self.close()
        if application is not None:
            application.quit()

    def _escape_pressed(self, _controller, keyval, _keycode, _state):
        if keyval != Gdk.KEY_Escape:
            return False
        # Escape matches Cancel. While Polkit is prompting, leave the key
        # for the authentication agent instead of closing or logging out.
        if self._state.in_flight:
            return False
        self._cancel()
        return True

    def _dismiss_after_success(self):
        self._success_logout_source_id = None
        if self._child_overlay:
            LOG.info("approved request acknowledged; closing overlay")
            self._close_overlay()
        else:
            LOG.info("approved request acknowledged; returning to login")
            self._logout()
        return GLib.SOURCE_REMOVE

    def _success_countdown_label(self, remaining):
        return f"{self._success_action_label} ({remaining})"

    def _tick_success_countdown(self):
        self._success_countdown_remaining -= 1
        if self._success_countdown_remaining <= 0:
            self._success_logout_source_id = None
            return self._dismiss_after_success()
        self._result_action.set_label(
            self._success_countdown_label(self._success_countdown_remaining),
        )
        return GLib.SOURCE_CONTINUE

    def _cancel_success_dismiss(self):
        if self._music is not None:
            self._music.cancel_fade(restore=False)
        if self._sizzle is not None:
            self._sizzle.cancel_fade(restore=False)
        if self._success_action_label is not None:
            self._result_action.set_label(self._success_action_label)
            self._success_action_label = None
        self._success_countdown_remaining = None
        if self._success_logout_source_id is None:
            return
        GLib.source_remove(self._success_logout_source_id)
        self._success_logout_source_id = None

    def _schedule_success_logout(self):
        self._cancel_success_dismiss()
        self._success_action_label = self._result_action.get_label()
        self._success_countdown_remaining = SUCCESS_COUNTDOWN_SECONDS
        self._result_action.set_label(
            self._success_countdown_label(SUCCESS_COUNTDOWN_SECONDS),
        )
        if self._music is not None:
            self._music.fade_out(SUCCESS_LOGOUT_DELAY_MS)
        if self._sizzle is not None:
            self._sizzle.fade_out(SUCCESS_LOGOUT_DELAY_MS)
        self._success_logout_source_id = GLib.timeout_add(
            1_000, self._tick_success_countdown,
        )

    def _bus_call(self, method, parameters, reply_signature, callback, timeout=30_000):
        if self._system_bus is None:
            raise RuntimeError("the preview does not have a broker connection")
        self._system_bus.call(
            BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
            GLib.VariantType.new(reply_signature), Gio.DBusCallFlags.NONE,
            timeout, None, callback,
        )

    def _load_users(self, *_args):
        if self._preview and not self._interactive_preview:
            users = PREVIEW_USERS[:1] if self._child_overlay else PREVIEW_USERS
            self._request_content.set_loading()
            self._request_content.set_accounts(users)
            self._request_content.set_approvers(PREVIEW_APPROVERS)
            return
        LOG.info("request-account discovery started overlay=%s", self._child_overlay)
        self._request_content.set_loading()
        if self._child_overlay:
            self._bus_call("GetOwnAccount", None, "(uss)", self._own_account_done)
        else:
            self._bus_call("ListManagedUsers", None, "(a(uss))", self._users_done)
        self._bus_call("ListApprovers", None, "(a(uss))", self._approvers_done)

    def _own_account_done(self, connection, result):
        try:
            uid, label, icon_file = connection.call_finish(result).unpack()
            LOG.info("own-account discovery completed account=[Child user]")
            self._request_content.set_accounts(((uid, label, icon_file),))
        except Exception as error:
            LOG.warning("own-account outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _users_done(self, connection, result):
        try:
            users, = connection.call_finish(result).unpack()
            LOG.info("managed-user discovery completed count=%d", len(users))
            self._request_content.set_accounts(users)
        except Exception as error:
            LOG.warning("users outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _approvers_done(self, connection, result):
        try:
            users, = connection.call_finish(result).unpack()
            LOG.info("approver discovery completed count=%d", len(users))
            self._request_content.set_approvers(users)
        except Exception as error:
            LOG.warning("approvers outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _load_preferences(self, target_uid):
        if self._preview and not self._interactive_preview:
            self._applying_preferences = True
            try:
                self._request_content.set_preferences(PREVIEW_PREFERENCES[target_uid])
                if self._child_overlay:
                    self._apply_mute(
                        self._request_content.muted_for_surface(self._mute_surface()),
                    )
            finally:
                self._applying_preferences = False
            return
        LOG.info("preferences load started target=[Child user]")
        self._bus_call(
            "GetPreferences", GLib.Variant("(u)", (target_uid,)), "(s)",
            lambda connection, result: self._preferences_done(
                target_uid, connection, result,
            ),
        )

    def _preferences_done(self, target_uid, connection, result):
        try:
            encoded, = connection.call_finish(result).unpack()
            if not self._request_content.is_selected_account(target_uid):
                return
            self._applying_preferences = True
            try:
                self._request_content.set_preferences(json.loads(encoded))
                self._apply_mute(
                    self._request_content.muted_for_surface(self._mute_surface()),
                )
            finally:
                self._applying_preferences = False
            LOG.info("preferences load completed target=[Child user]")
        except Exception as error:
            LOG.warning("preferences outcome=unavailable error_type=%s", type(error).__name__)

    def _persist_form_values(self):
        if (self._preview and not self._interactive_preview) or self._applying_preferences:
            return
        try:
            target_uid, _label, approver_uid, _seconds, _allow_soft = (
                self._request_content.selected()
            )
            selected, custom, allow_soft = self._request_content.selected_preferences()
        except ValueError:
            return
        try:
            self._bus_call(
                "UpdateRequestPreferences",
                GLib.Variant(
                    "(usdbu)",
                    (target_uid, selected, custom, allow_soft, approver_uid),
                ),
                "(s)", self._preferences_save_done,
            )
        except Exception as error:
            LOG.warning(
                "request preferences save failed error_type=%s",
                type(error).__name__,
            )

    def _persist_muted(self, muted):
        if (self._preview and not self._interactive_preview) or self._applying_preferences:
            return
        try:
            target_uid, *_rest = self._request_content.selected()
        except ValueError:
            return
        try:
            self._bus_call(
                "SetRequestMuted",
                GLib.Variant("(usb)", (target_uid, self._mute_surface(), muted)),
                "(s)", self._preferences_save_done,
            )
        except Exception as error:
            LOG.warning("mute save failed error_type=%s", type(error).__name__)

    def _preferences_save_done(self, connection, result):
        try:
            connection.call_finish(result)
        except Exception as error:
            LOG.warning(
                "request preferences outcome=unavailable error_type=%s",
                type(error).__name__,
            )

    def _request_access(self, *_args):
        if self._preview and not self._interactive_preview:
            try:
                self._request_content.selected()
            except ValueError as error:
                self._request_content.show_validation_error(str(error))
                return
            if self._child_overlay:
                self._show_child_success()
            else:
                self._show_result(
                    "Preview request",
                    "This is a visual preview; no access was requested.",
                )
            return
        if not self._state.begin():
            return
        try:
            target_uid, _target_label, approver_uid, duration_seconds, allow_soft = \
                self._request_content.selected()
            selected, custom, allow_soft = self._request_content.selected_preferences()
        except ValueError as error:
            self._state.finish()
            self._request_content.show_validation_error(str(error))
            return
        self._set_request_controls(False)
        LOG.info("target=[Child user] approver=[Administrator] duration_seconds=%d "
                 "allow_soft=%s overlay=%s stage=request",
                 duration_seconds, allow_soft, self._child_overlay)
        try:
            self._pending_request = (
                target_uid, approver_uid, duration_seconds, allow_soft,
            )
            self._bus_call(
                "UpdateRequestPreferences",
                GLib.Variant(
                    "(usdbu)",
                    (target_uid, selected, custom, allow_soft, approver_uid),
                ),
                "(s)", self._preferences_saved,
            )
        except Exception as error:
            self._request_failed(error)

    def _preferences_saved(self, connection, result):
        try:
            connection.call_finish(result)
            target_uid, approver_uid, duration_seconds, allow_soft = self._pending_request
            if self._child_overlay:
                self._bus_call(
                    "RequestOwnAccess",
                    GLib.Variant(
                        "(uub)", (approver_uid, duration_seconds, allow_soft),
                    ),
                    "(ssu)", self._request_done, REQUEST_TIMEOUT_MS,
                )
            else:
                self._bus_call(
                    "RequestAccess",
                    GLib.Variant(
                        "(uuub)",
                        (target_uid, approver_uid, duration_seconds, allow_soft),
                    ),
                    "(ss)", self._request_done, REQUEST_TIMEOUT_MS,
                )
        except Exception as error:
            self._request_failed(error)

    def _request_done(self, connection, result):
        try:
            unpacked = connection.call_finish(result).unpack()
            if self._child_overlay:
                correlation_id, outcome, _granted = unpacked
            else:
                correlation_id, outcome = unpacked
            if outcome not in {"approved", "denied", "cancelled"}:
                raise ValueError("broker returned malformed result")
            LOG.info("request=%s outcome=%s", correlation_id, outcome)
            if outcome == "approved":
                if self._child_overlay:
                    self._show_child_success()
                else:
                    self._show_result("Request approved", "")
                    self._schedule_success_logout()
            elif outcome == "cancelled":
                # Cancellation is not an error or a session transition.  The
                # administrator returns to the same kiosk request form without
                # an additional message.
                self._request_content.clear_validation_error()
                self._stack.set_visible_child_name("request")
            else:
                # A completed authorization attempt that was not approved
                # (for example, an incorrect password) is actionable, so keep
                # the request choices visible and show the error in place.
                self._request_content.show_validation_error("Request denied")
                self._stack.set_visible_child_name("request")
        except Exception as error:
            self._request_failed(error)
        finally:
            self._state.finish()
            self._set_request_controls(True)

    def _request_failed(self, error):
        LOG.warning("outcome=unavailable error_type=%s", type(error).__name__)
        self._state.finish()
        self._set_request_controls(True)
        self._show_error(error)

    def _set_request_controls(self, enabled):
        self._request_content.set_controls_sensitive(enabled)

    def _show_error(self, error):
        title, detail = public_error(error, child_overlay=self._child_overlay)
        if self._child_overlay:
            self._result_action.set_label("Close")
        self._show_result(title, detail)

    def _show_child_success(self):
        self._result_action.set_label(CHILD_SUCCESS_COPY)
        self._show_result(CHILD_SUCCESS_TITLE, "")
        self._schedule_success_logout()

    def _show_result(self, title, detail):
        self._result_title.set_text(title)
        self._result_detail.set_text(detail)
        self._result_detail.set_visible(bool(detail))
        if detail:
            self._result_view.remove_css_class(
                "oh-no-parent-control-compact-result",
            )
        else:
            self._result_view.add_css_class(
                "oh-no-parent-control-compact-result",
            )
        self._stack.set_visible_child_name("result")


class Application(Adw.Application):
    def __init__(self, *, preview=False, soundtrack=None, child_overlay=False,
                 window_factory=None):
        super().__init__(
            application_id=(
                "com.puffyslippers.OhNoParentControl.ChildRequest"
                if child_overlay else
                "com.puffyslippers.OhNoParentControl"
            ),
        )
        self._preview = preview
        self._soundtrack = soundtrack
        self._child_overlay = child_overlay
        self._window_factory = window_factory or RequestWindow
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._css_provider = None
        self._preview_monitor = None
        self._preview_reload_source_id = None
        self._preview_changed_paths = set()

    @staticmethod
    def _asset_path(name):
        return Path(__file__).with_name(name)

    def _load_stylesheet(self):
        self._css_provider.load_from_path(str(self._asset_path("style.css")))

    def _watch_preview_files(self):
        """Reload preview assets immediately and relaunch safely for Python edits."""
        if self._preview_monitor is not None:
            return
        directory = Gio.File.new_for_path(str(Path(__file__).parent))
        self._preview_monitor = directory.monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None,
        )
        self._preview_monitor.connect("changed", self._preview_file_changed)

    def _preview_file_changed(self, _monitor, file, other_file, event_type):
        if event_type not in {
            Gio.FileMonitorEvent.CHANGED,
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.MOVED_IN,
        }:
            return
        changed = {Path(file.get_path() or "")}
        if other_file is not None:
            changed.add(Path(other_file.get_path() or ""))
        relevant = {
            path for path in changed
            if path.name in {"style.css", "kiosk-background.jpeg"} or path.suffix == ".py"
        }
        if not relevant:
            return
        self._preview_changed_paths.update(relevant)
        if self._preview_reload_source_id is None:
            self._preview_reload_source_id = GLib.timeout_add(150, self._reload_preview)

    def _reload_preview(self):
        self._preview_reload_source_id = None
        changed_paths = self._preview_changed_paths
        self._preview_changed_paths = set()
        names = {path.name for path in changed_paths}
        if "style.css" in names:
            self._load_stylesheet()
            LOG.info("preview stylesheet reloaded")
        window = self.get_active_window()
        if "kiosk-background.jpeg" in names and window is not None:
            window._background.reload_texture()
            LOG.info("preview artwork reloaded")
        if any(path.suffix == ".py" for path in changed_paths):
            LOG.info("preview source changed; relaunching")
            os.execv(sys.executable, sys.orig_argv)
        return GLib.SOURCE_REMOVE

    def do_activate(self):
        window = self.get_active_window() or self._window_factory(
            self, preview=self._preview, soundtrack=self._soundtrack,
            child_overlay=self._child_overlay,
        )
        if self._css_provider is None:
            self._css_provider = Gtk.CssProvider()
            self._load_stylesheet()
            Gtk.StyleContext.add_provider_for_display(
                window.get_display(), self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        if self._preview:
            self._watch_preview_files()
        window.present()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview", action="store_true",
        help="render the kiosk UI with fixture data and no privileged services",
    )
    parser.add_argument(
        "--child-overlay", action="store_true",
        help="present the shared request GUI as a child-session overlay",
    )
    parser.add_argument(
        "--soundtrack", type=Path,
        help="soundtrack file to play instead of the installed kiosk soundtrack",
    )
    args = parser.parse_args(argv)
    configure_logging(
        preview=args.preview,
        component="child" if args.child_overlay else "kiosk",
    )
    LOG.info("kiosk app starting overlay=%s", args.child_overlay)
    return Application(
        preview=args.preview, soundtrack=args.soundtrack,
        child_overlay=args.child_overlay,
    ).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
