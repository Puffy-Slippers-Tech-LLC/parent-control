"""Libadwaita application for the GNOME Kiosk request station."""

from __future__ import annotations

import argparse
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

from .model import RequestState, public_error
from .request_content import RequestContent

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
# An authorization prompt remains open until the administrator responds.
# G_MAXINT is GIO's supported no-timeout value.
REQUEST_TIMEOUT_MS = GLib.MAXINT
# Keep the confirmation visible briefly before returning to GDM.
SUCCESS_LOGOUT_DELAY_MS = 3_000
GATEWAY_EFFECT_FRAME_MS = 33
# The form is centered in the window while the gateway in the artwork is
# slightly left of the image centre.  Shift the composed artwork just enough
# to centre the form within the gateway at every resolution.
GATEWAY_CENTERING_OFFSET = 0.03125
# Project the complete form as the flat surface mounted inside the gateway.
# The gateway's horizon crosses the middle of the form, so its upper edges
# descend to the right while its lower edges rise to the right.
GATEWAY_FORM_YAW_DEGREES = 10.0
GATEWAY_FORM_PERSPECTIVE_DEPTH = 1_200.0
PREVIEW_DEFAULT_WIDTH = 1918
PREVIEW_DEFAULT_HEIGHT = 1443
PREVIEW_USERS = ((1001, "Alex Morgan"), (1002, "Sam Rivera"))
PREVIEW_APPROVERS = ((1000, "Taylor Morgan"),)
PREVIEW_PREFERENCES = {
    "request": {
        "last_selected_duration": "1800",
        "last_custom_minutes": 30,
        "allow_soft_blocked_apps": False,
    },
}
LOG = logging.getLogger("oh-no-parent-control")


class BrokerLogHandler(logging.Handler):
    """Forward kiosk records to the broker-owned daily log."""

    def __init__(self):
        super().__init__()
        self._connection = None

    def emit(self, record):
        try:
            if self._connection is None:
                self._connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self._connection.call(
                BUS_NAME, OBJECT_PATH, INTERFACE, "LogEvent",
                GLib.Variant("(sss)", ("kiosk", record.levelname, self.format(record))),
                GLib.VariantType.new("()"), Gio.DBusCallFlags.NONE, 5_000, None, None,
            )
        except Exception:
            self._connection = None


class GatewayBackground(Gtk.Widget):
    """Static kiosk artwork with animated energy travelling through its gateway."""

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self._started_at = GLib.get_monotonic_time() / 1_000_000
        self._texture = self._load_texture()
        self._random = random.SystemRandom()
        self._lightning_bolts = []
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
        image_width = self._texture.get_width()
        image_height = self._texture.get_height()
        scale = max(width / image_width, height / image_height)
        rendered_width = image_width * scale
        rendered_height = image_height * scale
        image_bounds = Graphene.Rect().init(
            (width - rendered_width) / 2
            + rendered_width * GATEWAY_CENTERING_OFFSET,
            (height - rendered_height) / 2,
            rendered_width,
            rendered_height,
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
        """Create one non-repeating bolt from the background into the gate."""
        while True:
            source_x = self._random.uniform(0.03, 0.97)
            source_y = self._random.uniform(0.03, 0.97)
            # Keep origins out of the gateway and its foreground form.
            if abs(source_x - 0.5) > 0.27 or abs(source_y - 0.49) > 0.34:
                break
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

        if not self._lightning_bolts:
            self._lightning_bolts = [
                self._new_lightning_bolt(-index * 0.27)
                for index in range(4)
            ]

        for index, bolt in enumerate(self._lightning_bolts):
            if elapsed >= bolt["starts_at"] + bolt["duration"]:
                self._lightning_bolts[index] = self._new_lightning_bolt(
                    elapsed + self._random.uniform(0.08, 0.42),
                )

        for bolt in self._lightning_bolts:
            progress = (elapsed - bolt["starts_at"]) / bolt["duration"]
            if not 0 <= progress <= 1:
                continue
            source_x, source_y = bolt["source_x"] * width, bolt["source_y"] * height
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


def _gateway_form_projection(width, height):
    """Return the gateway's perspective transform around the form's centre."""
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


class GatewayAlignedRequest(Gtk.Widget):
    """Container that mounts the complete request form in the gateway plane."""

    def __init__(self, child):
        super().__init__(hexpand=True, vexpand=True)
        self._child = child
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        return self._child.measure(orientation, for_size)

    def do_size_allocate(self, width, height, baseline):
        _minimum_width, natural_width, _minimum_baseline, _natural_baseline = (
            self._child.measure(Gtk.Orientation.HORIZONTAL, -1)
        )
        child_width = min(width, natural_width)
        _minimum_height, natural_height, _minimum_baseline, _natural_baseline = (
            self._child.measure(Gtk.Orientation.VERTICAL, child_width)
        )
        child_height = min(height, natural_height)

        projection = _gateway_form_projection(child_width, child_height)
        projected_bounds = projection.transform_bounds(
            Graphene.Rect().init(0, 0, child_width, child_height),
        )
        placement = Graphene.Point().init(
            (width - projected_bounds.get_width()) / 2 - projected_bounds.get_x(),
            (height - projected_bounds.get_height()) / 2 - projected_bounds.get_y(),
        )
        transform = Gsk.Transform.new().translate(placement).transform(projection)
        self._child.allocate(child_width, child_height, baseline, transform)

    def do_snapshot(self, snapshot):
        self.snapshot_child(self._child, snapshot)

    def do_dispose(self):
        if self._child is not None:
            self._child.unparent()
            self._child = None
        Gtk.Widget.do_dispose(self)


def configure_logging(preview=False):
    """Use local logging for preview; production records belong to the broker."""
    handler = logging.StreamHandler() if preview else BrokerLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class RequestWindow(Adw.ApplicationWindow):
    def __init__(self, application, *, preview=False):
        super().__init__(application=application, title="Oh No! Parent Control")
        self.add_css_class("oh-no-parent-control-window")
        self.set_default_size(
            PREVIEW_DEFAULT_WIDTH if preview else 800,
            PREVIEW_DEFAULT_HEIGHT if preview else 600,
        )
        self._preview = preview
        self._state = RequestState()
        self._success_logout_source_id = None
        self._system_bus = None if preview else Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self._build()
        LOG.info("request station window initialized")
        if not preview:
            self.connect("map", lambda *_args: self.fullscreen())
        self._load_users()

    def _build(self):
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self._background = GatewayBackground()
        self._background.add_css_class("oh-no-parent-control-gateway-background")
        self._background.set_can_target(False)
        layout = Gtk.Overlay()
        layout.set_child(self._background)
        layout.add_overlay(self._stack)
        if self._preview:
            # The production kiosk is fullscreen, but its frameless preview
            # still needs a compositor-supported surface for moving it.
            drag_handle = Gtk.WindowHandle()
            drag_handle.set_child(layout)
            self.set_content(drag_handle)
        else:
            self.set_content(layout)
        self._request_content = RequestContent(
            self._request_access, self._logout, self._load_preferences,
        )
        self._request_surface = GatewayAlignedRequest(self._request_content)
        self._stack.add_named(self._request_surface, "request")

        self._result_view = self._page("Request result")
        self._result_title = Gtk.Label(css_classes=["oh-no-parent-control-page-title"])
        self._result_detail = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._result_view.append(self._result_title)
        self._result_view.append(self._result_detail)
        return_button = Gtk.Button(label="Return to Login")
        return_button.add_css_class("oh-no-parent-control-request-button")
        return_button.connect("clicked", self._logout)
        self._result_view.append(return_button)
        self._stack.add_named(self._result_view, "result")

    @staticmethod
    def _page(title):
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=24,
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
        )
        box.add_css_class("oh-no-parent-control-dialog")
        box.add_css_class("oh-no-parent-control-secondary-page")
        box.append(Gtk.Label(label=title, css_classes=["oh-no-parent-control-page-title"]))
        return box

    def _logout(self, *_args):
        if self._preview:
            self._stack.set_visible_child_name("request")
            return
        # OnSuccess=gnome-session-shutdown.target on the application unit turns
        # this clean exit into a supported kiosk-session logout back to GDM.
        LOG.info("return to login requested")
        self.get_application().quit()

    def _logout_after_success(self):
        self._success_logout_source_id = None
        LOG.info("approved request acknowledged; returning to login")
        self._logout()
        return GLib.SOURCE_REMOVE

    def _schedule_success_logout(self):
        if self._success_logout_source_id is not None:
            GLib.source_remove(self._success_logout_source_id)
        self._success_logout_source_id = GLib.timeout_add(
            SUCCESS_LOGOUT_DELAY_MS, self._logout_after_success,
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
        if self._preview:
            self._request_content.set_loading()
            self._request_content.set_accounts(PREVIEW_USERS)
            self._request_content.set_approvers(PREVIEW_APPROVERS)
            return
        LOG.info("request-account discovery started")
        self._request_content.set_loading()
        self._bus_call("ListManagedUsers", None, "(a(us))", self._users_done)
        self._bus_call("ListApprovers", None, "(a(us))", self._approvers_done)

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
        if self._preview:
            self._request_content.set_preferences(PREVIEW_PREFERENCES)
            return
        LOG.info("preferences load started target_uid=%d", target_uid)
        self._bus_call(
            "GetPreferences", GLib.Variant("(u)", (target_uid,)), "(s)",
            self._preferences_done,
        )

    def _preferences_done(self, connection, result):
        try:
            encoded, = connection.call_finish(result).unpack()
            self._request_content.set_preferences(json.loads(encoded))
            LOG.info("preferences load completed")
        except Exception as error:
            LOG.warning("preferences outcome=unavailable error_type=%s", type(error).__name__)

    def _request_access(self, *_args):
        if self._preview:
            try:
                self._request_content.selected()
            except ValueError as error:
                self._request_content.show_validation_error(str(error))
                return
            self._show_result(
                "Preview request",
                "This is a visual preview; no access was requested.",
            )
            return
        if not self._state.begin():
            return
        try:
            target_uid, target_label, approver_uid, duration_seconds, allow_soft = \
                self._request_content.selected()
            selected, custom, allow_soft = self._request_content.selected_preferences()
        except ValueError as error:
            self._state.finish()
            self._request_content.show_validation_error(str(error))
            return
        self._set_request_controls(False)
        self._requested_label = target_label
        LOG.info("target_uid=%d approver_uid=%d duration_seconds=%d "
                 "allow_soft=%s stage=request", target_uid, approver_uid,
                 duration_seconds, allow_soft)
        try:
            self._pending_request = (
                target_uid, approver_uid, duration_seconds, allow_soft,
            )
            self._bus_call(
                "UpdateRequestPreferences",
                GLib.Variant("(usdb)", (target_uid, selected, custom, allow_soft)),
                "(s)", self._preferences_saved,
            )
        except Exception as error:
            self._request_failed(error)

    def _preferences_saved(self, connection, result):
        try:
            connection.call_finish(result)
            target_uid, approver_uid, duration_seconds, allow_soft = self._pending_request
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
            correlation_id, outcome = connection.call_finish(result).unpack()
            if outcome not in {"approved", "denied", "cancelled"}:
                raise ValueError("broker returned malformed result")
            LOG.info("request=%s outcome=%s", correlation_id, outcome)
            if outcome == "approved":
                self._show_result(
                    "Request approved", f"The requested access is ready for {self._requested_label}."
                )
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
        title, detail = public_error(error)
        self._show_result(title, detail)

    def _show_result(self, title, detail):
        self._result_title.set_text(title)
        self._result_detail.set_text(detail)
        self._stack.set_visible_child_name("result")


class Application(Adw.Application):
    def __init__(self, *, preview=False):
        super().__init__(application_id="com.puffyslippers.OhNoParentControl")
        self._preview = preview
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
        window = self.get_active_window() or RequestWindow(self, preview=self._preview)
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
    args = parser.parse_args(argv)
    configure_logging(preview=args.preview)
    LOG.info("kiosk app starting")
    return Application(preview=args.preview).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
