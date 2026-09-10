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
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gsk, Gtk

from common.oh_no_parent_control_ui.about import AboutDialog, app_name, open_help
from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.duration import format_duration
from common.oh_no_parent_control_ui.errors import (
    ErrorHandler, install_exception_hooks, show_startup_error,
)
from common.oh_no_parent_control_ui.test_identities import preview_users

from .model import RequestState, public_error
from .request_content import RequestContent
from .selection_store import SelectionStore
from .snowflakes import GATEWAY_OUTER_BOUNDS, SnowflakeField
from .floating_islands import FloatingIslands
from .lava import LavaBands
from .lightning import LightningDischarge
from .thunder import LightningAudio
from .chrome import (
    ABOUT, BOARD_CHAIN_ANCHOR_END_INSET, BOARD_CHAIN_ANCHOR_SIDE_INSET, HELP,
    MENU, SPEAKER, SPEAKER_MUTED, ArmoredButton, ArmoredMenuButton, HudIconFrame,
    HudMenuBoard, HudMenuStem, MetalBoard, PixelIcon,
    paint_board_frame,
)

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
# An authorization prompt remains open until the administrator responds.
# G_MAXINT is GIO's supported no-timeout value.
REQUEST_TIMEOUT_MS = GLib.MAXINT
# Keep the confirmation visible briefly before returning to GDM or
# closing the child overlay. Fade any remaining thunder over this interval.
SUCCESS_LOGOUT_DELAY_MS = 3_000
SUCCESS_COUNTDOWN_SECONDS = SUCCESS_LOGOUT_DELAY_MS // 1_000
CHILD_SUCCESS_TITLE = "Time granted"
CHILD_SUCCESS_COPY = "Time granted, Close"
GATEWAY_EFFECT_FRAME_MS = 33
# Keep the gateway separate from the side scenery when fitting the artwork.
# These cuts pass through empty sky beside the rails, outside every island.
GATEWAY_SCENE_CUTS = (0.27, 0.67)
GATEWAY_WIDTH_FRACTION = 0.40
# Native dimensions and measured corners of the gateway opening.  These points
# sit on the innermost purple edge, rather than on the outer cyan frame. Keeping
# them in source-image space lets the anchors follow the central artwork band.
GATEWAY_ARTWORK_WIDTH = 3_840
GATEWAY_ARTWORK_HEIGHT = 2_160
# The six intended formations in the supplied artwork: four on the left and
# two on the right. Each point is the visible tip of a crystal, in source-image
# fractions, so an ejection visibly starts at its crystal rather than in the
# surrounding cluster. Each point follows the fitting of its own scenery band.
CRYSTAL_LIGHTNING_TIPS = (
    (272 / 1672, 90 / 941),  # floating upper-left formation
    (164 / 1672, 314 / 941),  # left pedestal formation
    (298 / 1672, 567 / 941),  # lower-left pedestal formation
    (0.077, 0.873),  # foreground bottom-left formation
    (1320 / 1672, 358 / 941),  # right pedestal formation
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
    """Map the central artwork without magnifying/cropping the side islands.

    A readable minimum matters on small windows; desktop widths leave most
    of the scene to the crystals. The side bands fill their own allocations.
    """
    left, _top, right, _bottom = GATEWAY_OUTER_BOUNDS
    gateway_width = min(
        width * 0.88, max(460, min(640, width * GATEWAY_WIDTH_FRACTION)),
    )
    rendered_width = gateway_width / (right - left)
    return (
        width / 2 - (left + right) / 2 * rendered_width,
        0, rendered_width, height,
    )


def _gateway_scene_regions(width, height):
    """Three seamless source bands; retain both complete sides of the artwork.

    Each result contains its screen clip and the full texture's affine bounds.
    The same bounds position the original pixels and animated island masks.
    """
    image_x, image_y, image_width, image_height = _gateway_artwork_geometry(width, height)
    first, second = GATEWAY_SCENE_CUTS
    source_edges = (0, first, second, 1)
    screen_edges = (0, image_x + first * image_width,
                    image_x + second * image_width, width)
    regions = []
    for source_left, source_right, left, right in zip(
            source_edges, source_edges[1:], screen_edges, screen_edges[1:]):
        texture_width = (right - left) / (source_right - source_left)
        regions.append(((left, 0, right - left, height), (
            left - source_left * texture_width, image_y, texture_width, image_height,
        )))
    return tuple(regions)


def _gateway_scene_point(width, height, x, y):
    """Place an effect endpoint using its source band, including side crystals."""
    if x < GATEWAY_SCENE_CUTS[0]:
        band = 0
    elif x > GATEWAY_SCENE_CUTS[1]:
        band = 2
    else:
        band = 1
    _clip, artwork = _gateway_scene_regions(width, height)[band]
    image_x, image_y, image_width, image_height = artwork
    return image_x + x * image_width, image_y + y * image_height


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


class GatewayBackground(Gtk.Widget):
    """Gateway artwork with lava heat, floating islands, snow and lightning."""

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self._started_at = GLib.get_monotonic_time() / 1_000_000
        self._texture = self._load_texture()
        self._lava = LavaBands(self._texture)
        self._floating_islands = FloatingIslands(
            self._texture, self._load_texture("kiosk-background-clear.png"),
        )
        self._snowflakes = SnowflakeField()
        self._random = random.SystemRandom()
        self._lightning_bolts = []
        self._next_lightning_burst_at = 0.0
        self._lightning_enabled = False
        self._lightning_audio = None
        self._frame_source_id = GLib.timeout_add(
            GATEWAY_EFFECT_FRAME_MS, self._next_frame,
        )
        self.connect("destroy", self._stop_animation)

    @staticmethod
    def _load_texture(name="kiosk-background-still.png"):
        try:
            image_file = Gio.File.new_for_path(
                str(Path(__file__).with_name(name)),
            )
            return Gdk.Texture.new_from_file(image_file)
        except GLib.Error as error:
            LOG.warning(
                "kiosk background unavailable asset=%s error_type=%s",
                name, type(error).__name__,
            )
            return None

    def reload_texture(self):
        """Refresh the preview artwork without rebuilding the window."""
        self._texture = self._load_texture()
        self._lava = LavaBands(self._texture)
        self._floating_islands = FloatingIslands(
            self._texture, self._load_texture("kiosk-background-clear.png"),
        )
        self.queue_draw()

    def _next_frame(self):
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _stop_animation(self, *_args):
        if self._frame_source_id is not None:
            GLib.source_remove(self._frame_source_id)
            self._frame_source_id = None

    def set_lightning_audio(self, play_thunder):
        """Connect bolt starts to the window-owned, muteable audio effect."""
        self._lightning_audio = play_thunder

    def set_lightning_enabled(self, enabled):
        """Show lightning only while request-screen media is enabled."""
        self._lightning_enabled = bool(enabled)
        self._lightning_bolts.clear()
        # Enabling begins a fresh burst; disabling removes active and queued
        # bolts immediately so a muted screen cannot retain a fading strike.
        self._next_lightning_burst_at = 0.0
        self.queue_draw()
        LOG.info("gateway lightning enabled=%s", self._lightning_enabled)

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
        artwork = _gateway_artwork_geometry(width, height)
        for clip, region in _gateway_scene_regions(width, height):
            snapshot.push_clip(Graphene.Rect().init(*clip))
            image_bounds = Graphene.Rect().init(*region)
            snapshot.append_texture(self._texture, image_bounds)
            self._floating_islands.draw(snapshot, region, now)
            snapshot.pop()
        self._lava.draw(snapshot, artwork, now)

        # A low-opacity vignette preserves legibility while allowing the
        # supplied artwork to remain prominent.
        snapshot.append_color(
            Gdk.RGBA(red=0.02, green=0.03, blue=0.09, alpha=0.24),
            bounds,
        )
        self._snowflakes.configure(width, height, artwork)
        self._snowflakes.draw(snapshot.append_cairo(bounds), now)
        self._append_gateway_energy(snapshot, width, height, now)

    def _new_lightning_bolt(self, starts_at):
        """Anchor an angular discharge to a crystal and the nearest gate rail."""
        source_index = self._random.randrange(len(CRYSTAL_LIGHTNING_TIPS))
        source_x, source_y = CRYSTAL_LIGHTNING_TIPS[source_index]
        top, bottom = (
            (GATEWAY_INNER_CORNERS[0], GATEWAY_INNER_CORNERS[3])
            if source_x < GATEWAY_INNER_CORNERS[0][0]
            else (GATEWAY_INNER_CORNERS[1], GATEWAY_INNER_CORNERS[2])
        )
        target_y = max(
            top[1] + 0.045,
            min(bottom[1] - 0.045, source_y + self._random.uniform(-0.15, 0.15)),
        )
        channel = LightningDischarge(self._random)
        return {
            "starts_at": starts_at,
            "duration": channel.duration,
            "source_x": source_x,
            "source_y": source_y,
            "source_index": source_index,
            "target_x": top[0],
            "target_y": target_y,
            "channel": channel,
        }

    def _launch_lightning_burst(self, elapsed):
        """Leave irregular quiet intervals between short crystal discharges."""
        ejection_count = self._random.choices((1, 2, 3), weights=(6, 3, 1))[0]
        starts_at = elapsed + self._random.uniform(0.08, 0.3)
        for _ejection in range(ejection_count):
            bolt = self._new_lightning_bolt(starts_at)
            self._lightning_bolts.append(bolt)
            starts_at += bolt["duration"] + self._random.uniform(0.10, 0.32)
        self._next_lightning_burst_at = starts_at + self._random.uniform(0.9, 2.4)
        LOG.debug(
            "gateway lightning burst strikes=%d next_burst_in_ms=%d",
            ejection_count, int((self._next_lightning_burst_at - elapsed) * 1_000),
        )

    def _append_gateway_energy(self, snapshot, width, height, elapsed):
        """Flash stable, forked channels in the artwork's coordinate space."""
        if not self._lightning_enabled:
            return

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
            age = elapsed - bolt["starts_at"]
            if age < 0:
                continue
            source_x, source_y = _gateway_scene_point(
                width, height, bolt["source_x"], bolt["source_y"],
            )
            channel = bolt["channel"]
            active = channel.active_flash(age)
            if active is not None and bolt.get("audible_flash") != active[0]:
                flash_index, flash = active
                bolt["audible_flash"] = flash_index
                if self._lightning_audio is not None:
                    self._lightning_audio(
                        flash.light(age),
                        max(-0.8, min(0.8, 2 * source_x / width - 1)),
                    )
            source_y += self._floating_islands.offset(
                bolt["source_index"], elapsed,
            ) * image_height
            target = (
                image_x + bolt["target_x"] * image_width,
                image_y + bolt["target_y"] * image_height,
            )
            channel.draw(
                context, (source_x, source_y), target, image_width / 1672, age,
            )


def _gateway_form_projection(width, height):
    """Apply the gateway perspective in GTK logical coordinates, without zoom."""
    return (
        Gsk.Transform.new()
        .translate(Graphene.Point().init(width / 2, height / 2))
        .perspective(GATEWAY_FORM_PERSPECTIVE_DEPTH)
        .rotate_3d(
            GATEWAY_FORM_YAW_DEGREES,
            Graphene.Vec3().init(0, 1, 0),
        )
        .translate(Graphene.Point().init(-width / 2, -height / 2))
    )


class ResponsiveHud(Gtk.Widget):
    """Place corner controls at their native GTK size as the window changes."""

    def __init__(self, child):
        super().__init__(hexpand=True, vexpand=True)
        self._child = child
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        return (0, 0, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        child_width = self._child.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
        child_height = self._child.measure(Gtk.Orientation.VERTICAL, child_width)[1]
        margin = 24
        transform = Gsk.Transform.new().translate(Graphene.Point().init(
            width - child_width - margin, margin,
        ))
        self._child.allocate(child_width, child_height, baseline, transform)

    def do_snapshot(self, snapshot):
        self.snapshot_child(self._child, snapshot)

    def do_contains(self, x, y):
        # Leave the rest of this full-window overlay available to the form.
        valid, bounds = self._child.compute_bounds(self)
        return valid and bounds.contains_point(Graphene.Point().init(x, y))


class RequestViewport(Gtk.ScrolledWindow):
    """Keep the iron rails and chain lugs visible while content scrolls."""

    def do_snapshot(self, snapshot):
        Gtk.ScrolledWindow.do_snapshot(self, snapshot)
        paint_board_frame(snapshot, self.get_width(), self.get_height())


class GatewayAlignedRequest(Gtk.Widget):
    """Container that mounts the complete request form in the gateway plane."""

    def __init__(self, child):
        super().__init__(hexpand=True, vexpand=True)
        self._child = child
        self._form_corners = ()
        self._last_layout = None
        self._viewport = RequestViewport(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.EXTERNAL,
            overlay_scrolling=False,
        )
        self._viewport.add_css_class("oh-no-parent-control-request-viewport")
        if isinstance(child, MetalBoard):
            child.frame_visible = False
        self._viewport.set_child(child)
        self._viewport.set_parent(self)
        # A vertical scrollbar can use the projected screen rectangle directly.
        # Keeping this narrow input target outside the 3D allocation avoids
        # 3D coordinate conversion shifting its hit region into the form.
        self._scrollbar = Gtk.Scrollbar(
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=self._viewport.get_vadjustment(),
        )
        self._scrollbar.set_parent(self)
        self._scrollbar.set_visible(False)

    def do_measure(self, orientation, for_size):
        # Natural form dimensions must not force a fullscreen window beyond
        # the monitor's bounds. The viewport owns overflow in either surface.
        return (0, 0, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        # Allocations are already in GTK logical pixels. Enlarging the whole
        # render tree with the window makes a high-resolution desktop look
        # like a stretched low-resolution one and compounds monitor scaling.
        # Keep native control sizes; reflow and scroll when space is limited.
        corners = _gateway_inner_corners(width, height)
        left, right = corners[0][0], corners[1][0]
        opening_top = max(corners[0][1], corners[1][1])
        opening_bottom = min(corners[2][1], corners[3][1])
        # Reserve a visible run of chain above and below the board. Constrain
        # its projected bounds to the opening, not just to the fullscreen window.
        gap = (opening_bottom - opening_top) * 0.07
        top = max(opening_top + gap, 108 if width < 1000 else 0)
        available_width = max(1, right - left - 8)
        available_height = max(1, opening_bottom - gap - top)
        # Leave room for the perspective's wider near edge and board shadow.
        child_width = max(1, min(384, int(available_width / 1.04)))
        self._child.set_margin_end(0)
        if isinstance(self._child, RequestContent):
            self._child.set_layout_width(child_width)
        _minimum_height, natural_height, _minimum_baseline, _natural_baseline = (
            self._child.measure(Gtk.Orientation.VERTICAL, child_width)
        )
        near_edge = 1 - math.sin(math.radians(GATEWAY_FORM_YAW_DEGREES)) * (
            child_width / 2 / GATEWAY_FORM_PERSPECTIVE_DEPTH
        )
        maximum_height = max(1, int(available_height * near_edge))
        scrolling = natural_height > maximum_height
        self._scrollbar.set_visible(scrolling)
        if scrolling:
            scrollbar_width = max(15, self._scrollbar.measure(Gtk.Orientation.HORIZONTAL, -1)[0])
            self._child.set_margin_end(scrollbar_width + 16)
            if isinstance(self._child, RequestContent):
                self._child.set_layout_width(child_width - scrollbar_width - 16)
            natural_height = self._child.measure(Gtk.Orientation.VERTICAL, child_width)[1]
        child_height = min(natural_height, maximum_height)

        projection = _gateway_form_projection(child_width, child_height)
        projected_bounds = projection.transform_bounds(
            Graphene.Rect().init(0, 0, child_width, child_height),
        )
        placement = Graphene.Point().init(
            (left + right - projected_bounds.get_width()) / 2
            - projected_bounds.get_x(),
            top + (available_height - projected_bounds.get_height()) / 2
            - projected_bounds.get_y(),
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
        self._viewport.allocate(child_width, child_height, baseline, transform)
        if scrolling:
            bar_height = max(1, child_height - 36)
            bar_bounds = transform.transform_bounds(Graphene.Rect().init(
                child_width - scrollbar_width - 16, 18, scrollbar_width, bar_height,
            ))
            bar_transform = Gsk.Transform.new().translate(Graphene.Point().init(
                bar_bounds.get_x(), bar_bounds.get_y(),
            )).scale(bar_bounds.get_width() / scrollbar_width,
                     bar_bounds.get_height() / bar_height)
            self._scrollbar.allocate(scrollbar_width, bar_height, baseline, bar_transform)
        monitor_scale = self.get_scale_factor()
        native = self.get_native()
        surface = native.get_surface() if native else None
        surface_scale = surface.get_scale() if surface else float(monitor_scale)
        layout = (width, height, child_width, child_height, natural_height,
                  monitor_scale, surface_scale)
        if layout != self._last_layout:
            LOG.debug(
                "request layout viewport=%dx%d board=%dx%d monitor-scale=%d "
                "surface-scale=%.3f scroll=%s "
                "gateway-width=%.0f opening-height=%.0f chain-gap=%.0f",
                width, height, child_width, child_height, monitor_scale,
                surface_scale, natural_height > child_height,
                _gateway_artwork_geometry(width, height)[2]
                * (GATEWAY_OUTER_BOUNDS[2] - GATEWAY_OUTER_BOUNDS[0]),
                opening_bottom - opening_top, gap,
            )
            self._last_layout = layout

    def do_snapshot(self, snapshot):
        self._append_gateway_chains(snapshot)
        self.snapshot_child(self._viewport, snapshot)
        if self._scrollbar.get_visible():
            self.snapshot_child(self._scrollbar, snapshot)

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


def _time_estimate_label(seconds):
    return f"Estimated time remaining if approved: {format_duration(seconds)}"


class RequestWindow(Adw.ApplicationWindow):
    def __init__(self, application, *, preview=False,
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
        self._errors = ErrorHandler(self, "Child App" if child_overlay else "Kiosk App")
        self._error_report = None
        self._applying_preferences = False
        self._state = RequestState()
        self._estimate_revision = 0
        self._estimate_in_flight = False
        self._estimate_debounce_id = 0
        self._estimate_refresh_id = 0
        self._estimate_closed = False
        self._success_logout_source_id = None
        self._success_countdown_remaining = None
        self._success_action_label = None
        self._system_bus = (
            broker_connection if broker_connection is not None else
            (None if preview else Gio.bus_get_sync(Gio.BusType.SYSTEM, None))
        )
        self._build()
        self._thunder = LightningAudio()
        self._background.set_lightning_audio(self._thunder.play)
        # Start muted before playback so neither production nor either preview
        # surface can emit audio while preferences are loading.
        self._apply_mute(True)
        self.connect("destroy", self._on_destroy)
        LOG.info(
            "request station window initialized overlay=%s",
            child_overlay,
        )
        if not preview or child_overlay or os.environ.get("ONPC_PREVIEW_SCREEN_FD"):
            self.fullscreen()
            self.connect("map", lambda *_args: self.fullscreen())
        if preview and os.environ.get("ONPC_PREVIEW_SCREEN_FD"):
            from .preview_screen import notify_screen_ready
            self.connect("map", lambda *_: GLib.timeout_add(100, notify_screen_ready, self))
        self._load_users()
        self._estimate_refresh_id = GLib.timeout_add_seconds(
            30, self._refresh_time_estimate,
        )

    def _on_destroy(self, *_args):
        self._estimate_closed = True
        for source_id in (self._estimate_debounce_id, self._estimate_refresh_id):
            if source_id:
                GLib.source_remove(source_id)
        self._estimate_debounce_id = self._estimate_refresh_id = 0
        self._cancel_success_dismiss()
        if self._thunder is not None:
            self._thunder.close()
            self._thunder = None

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
        if self._preview:
            from .preview_screen import show_screen_dialog
            screen_item = self._hud_menu_item("Change Screens", MENU)
            describe_control(screen_item, "Change Screens", "Choose the preview screen resolution and display scale.")
            screen_item.connect("clicked", lambda *_: self._activate_help_menu(
                help_popover, lambda: show_screen_dialog(self),
            ))
            menu_actions.append(screen_item)
        menu_board.append(menu_actions)
        self._muted = False
        self._mute_icon = PixelIcon(SPEAKER, display_size=28, label="")
        self._mute_icon.set_halign(Gtk.Align.CENTER)
        self._mute_icon.set_valign(Gtk.Align.CENTER)
        self._mute_button = ArmoredButton(
            armor_kind="hud", tooltip_text="Mute sound and lightning",
        )
        describe_control(
            self._mute_button, "Mute request-screen sound",
            "Turn lightning and its thunder sound on or off.",
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
        top_controls = Gtk.Box(spacing=18)
        top_controls.append(self._mute_button)
        top_controls.append(menu_button)
        layout.add_overlay(ResponsiveHud(top_controls))
        if self._preview and not self._child_overlay and not os.environ.get("ONPC_PREVIEW_SCREEN_FD"):
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
            on_values_changed=self._form_values_changed,
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
        self._result_action.connect("clicked", self._result_dismissed)
        self._result_view.append(self._result_action)
        self._report_row = Gtk.Button(
            hexpand=True, visible=False, margin_start=10, margin_end=10,
            css_classes=["oh-no-parent-control-app-filter-toggle"],
        )
        report_content = Gtk.Box(spacing=12)
        report_label = Gtk.Label(
            label="Report this error", xalign=0, hexpand=True, wrap=True,
            css_classes=["oh-no-parent-control-app-filter-label"],
        )
        self._report_error = Gtk.Switch(active=True, valign=Gtk.Align.CENTER)
        self._report_error.set_can_target(False)
        report_label.set_mnemonic_widget(self._report_error)
        description = "Review an error report before closing or returning to login."
        describe_control(self._report_row, "Report this error", description)
        describe_control(self._report_error, "Report this error", description)
        report_content.append(report_label)
        report_content.append(self._report_error)
        self._report_row.set_child(report_content)
        self._report_row.connect("clicked", lambda *_: self._report_error.set_active(
            not self._report_error.get_active(),
        ))
        self._result_view.append(self._report_row)
        escape = Gtk.EventControllerKey()
        escape.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        escape.connect("key-pressed", self._escape_pressed)
        self.add_controller(escape)
        # Keep every outcome, including the post-authorization confirmation,
        # mounted in the gateway plane.  Adding this box directly to the stack
        # would bypass the yaw and perspective used by the request form.
        self._result_surface = GatewayAlignedRequest(self._result_view)
        self._stack.add_named(self._result_surface, "result")

    def _result_dismissed(self, *_args):
        if self._error_report is not None and self._report_error.get_active():
            self._errors.present(self._error_report, on_close=self._cancel)
        else:
            self._cancel()

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
        self._thunder.set_muted(muted)
        self._background.set_lightning_enabled(not muted)
        self._mute_icon.set_pixels(SPEAKER_MUTED if muted else SPEAKER)
        self._mute_button.set_tooltip_text(
            "Unmute sound and lightning" if muted else "Mute sound and lightning"
        )
        if muted:
            self._mute_button.add_css_class("oh-no-parent-control-hud-muted")
        else:
            self._mute_button.remove_css_class("oh-no-parent-control-hud-muted")
        LOG.info(
            "request-screen media muted=%s lightning_enabled=%s overlay=%s",
            muted, not muted, self._child_overlay,
        )

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
            if self._thunder is not None:
                self._thunder.cancel_fade()
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
        if self._stack.get_visible_child_name() == "result":
            self._result_dismissed()
        else:
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
        if self._thunder is not None:
            self._thunder.cancel_fade(restore=False)
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
        if self._thunder is not None:
            self._thunder.fade_out(SUCCESS_LOGOUT_DELAY_MS)
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
            self._queue_time_estimate()
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
            self._queue_time_estimate()
        except Exception as error:
            LOG.warning("approvers outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _load_preferences(self, target_uid):
        self._queue_time_estimate()
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
            self._queue_time_estimate()
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
            self._queue_time_estimate()
            LOG.info("preferences load completed target=[Child user]")
        except Exception as error:
            LOG.warning("preferences outcome=unavailable error_type=%s", type(error).__name__)
            self._show_error(error)

    def _form_values_changed(self):
        self._queue_time_estimate()
        self._persist_form_values()

    def _queue_time_estimate(self):
        # Invalidate replies immediately, including when the form becomes invalid.
        self._estimate_revision += 1
        self._request_content.set_time_estimate("Calculating time estimate…")
        if self._estimate_debounce_id:
            GLib.source_remove(self._estimate_debounce_id)
        self._estimate_debounce_id = GLib.timeout_add(250, self._time_estimate_debounced)

    def _time_estimate_debounced(self):
        self._estimate_debounce_id = 0
        self._refresh_time_estimate()
        return GLib.SOURCE_REMOVE

    def _refresh_time_estimate(self):
        if self._estimate_closed:
            return GLib.SOURCE_REMOVE
        if (self._state.in_flight or
                self._stack.get_visible_child_name() != "request"):
            return GLib.SOURCE_CONTINUE
        selection = self._request_content.time_estimate_selection()
        if selection is None:
            return GLib.SOURCE_CONTINUE
        uid, seconds = selection
        if seconds == 0:
            self._request_content.set_time_estimate("If approved, access until midnight.")
            return GLib.SOURCE_CONTINUE
        if self._estimate_in_flight:
            return GLib.SOURCE_CONTINUE
        if self._preview and not self._interactive_preview:
            self._request_content.set_time_estimate(_time_estimate_label(15 * 60 + seconds))
            return GLib.SOURCE_CONTINUE
        revision = self._estimate_revision
        self._estimate_in_flight = True
        try:
            self._bus_call(
                "GetTimeStatus", GLib.Variant("(uu)", (uid, seconds)), "(uuuu)",
                lambda connection, result: self._time_estimate_done(
                    revision, selection, connection, result,
                ),
            )
        except Exception as error:
            self._finish_time_estimate(revision, selection, error=error)
        return GLib.SOURCE_CONTINUE

    def _time_estimate_done(self, revision, selection, connection, result):
        try:
            _daily, _grant, _additional, calculated = connection.call_finish(result).unpack()
        except Exception as error:
            self._finish_time_estimate(revision, selection, error=error)
        else:
            self._finish_time_estimate(revision, selection, seconds=calculated)

    def _finish_time_estimate(self, revision, selection, *, seconds=None, error=None):
        self._estimate_in_flight = False
        if self._estimate_closed:
            return
        if (revision != self._estimate_revision or
                selection != self._request_content.time_estimate_selection()):
            # Coalesce changes made during a broker read into one fresh request.
            if not self._estimate_debounce_id:
                self._refresh_time_estimate()
            return
        if error is not None:
            LOG.warning("time estimate unavailable target=[Child user] error_type=%s",
                        type(error).__name__)
            self._request_content.set_time_estimate("Time estimate unavailable")
            self._errors.handle(error, "Time estimate unavailable",
                                "The estimated remaining time could not be loaded.")
        else:
            LOG.debug("time estimate loaded target=[Child user] seconds=%d", seconds)
            self._request_content.set_time_estimate(_time_estimate_label(seconds))

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
            self._errors.handle(error, "Settings could not be saved",
                                "Your request choices could not be saved. Please try again later.")

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
            self._errors.handle(error, "Settings could not be saved",
                                "Your sound preference could not be saved. Please try again later.")

    def _preferences_save_done(self, connection, result):
        try:
            connection.call_finish(result)
        except Exception as error:
            LOG.warning(
                "request preferences outcome=unavailable error_type=%s",
                type(error).__name__,
            )
            self._errors.handle(error, "Settings could not be saved",
                                "Your request preferences could not be saved. Please try again later.")

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
            self._queue_time_estimate()

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
        self._error_report = self._errors.capture(error, title, detail)
        self._report_error.set_active(True)
        self._report_row.set_visible(True)

    def _show_child_success(self):
        self._result_action.set_label(CHILD_SUCCESS_COPY)
        self._show_result(CHILD_SUCCESS_TITLE, "")
        self._schedule_success_logout()

    def _show_result(self, title, detail):
        self._error_report = None
        self._report_row.set_visible(False)
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
    def __init__(self, *, preview=False, child_overlay=False,
                 window_factory=None, report_error=None):
        super().__init__(
            application_id=(
                "com.puffyslippers.OhNoParentControl.ChildRequest"
                if child_overlay else
                "com.puffyslippers.OhNoParentControl"
            ),
            flags=(Gio.ApplicationFlags.NON_UNIQUE if report_error is not None
                   else Gio.ApplicationFlags.DEFAULT_FLAGS),
        )
        self._report_error = report_error
        self._preview = preview
        self._child_overlay = child_overlay
        self._window_factory = window_factory or RequestWindow
        install_exception_hooks(self, "Child App" if child_overlay else "Kiosk App")
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
            if path.name in {
                "style.css", "kiosk-background-still.png", "kiosk-background-clear.png",
            } or path.suffix == ".py"
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
        if (
            names & {"kiosk-background-still.png", "kiosk-background-clear.png"}
            and window is not None
        ):
            window._background.reload_texture()
            LOG.info("preview artwork reloaded")
        if any(path.suffix == ".py" for path in changed_paths):
            LOG.info("preview source changed; relaunching")
            os.execv(sys.executable, sys.orig_argv)
        return GLib.SOURCE_REMOVE

    def do_activate(self):
        if self._report_error is not None:
            show_startup_error(self, "Child App", self._report_error)
            return
        window = self.get_active_window() or self._window_factory(
            self, preview=self._preview,
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
        "--error-report-stdin", action="store_true",
        help="review a Child App error received on standard input (requires --child-overlay)",
    )
    args = parser.parse_args(argv)
    if args.error_report_stdin and not args.child_overlay:
        parser.error("--error-report-stdin requires --child-overlay")
    report_error = RuntimeError(sys.stdin.read(3500)) if args.error_report_stdin else None
    configure_logging(
        preview=args.preview,
        component="child" if args.child_overlay else "kiosk",
    )
    LOG.info("kiosk app starting overlay=%s", args.child_overlay)
    return Application(
        preview=args.preview,
        child_overlay=args.child_overlay,
        report_error=report_error,
    ).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
