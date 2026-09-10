"""Exercise the actual host-facing viewer and retain its decoded RGB frame."""

import json
import os
from pathlib import Path

import gi
gi.require_version("Graphene", "1.0")
from gi.repository import Graphene

from kiosk.oh_no_parent_control_kiosk.preview_viewer import Viewer, Gtk, GLib, content_rectangle, run

output = Path(os.environ["ONPC_FIDELITY_VIEWER"])
app_output = Path(os.environ["ONPC_FIDELITY_APP"])


class Probe(Viewer):
    def _frame(self, paintable):
        was_ready = self.ready
        super()._frame(paintable)
        if self.ready and not was_ready:
            GLib.timeout_add(1500, self.inspect)

    def inspect(self):
        if not app_output.exists():
            return True
        snapshot = Gtk.Snapshot.new()
        self.capture.paintable.snapshot(snapshot, self.screen.width, self.screen.height)
        texture = self.window.get_renderer().render_texture(snapshot.to_node(), Graphene.Rect().init(
            0, 0, self.screen.width, self.screen.height))
        assert texture.save_to_png(str(output.with_suffix(".png")))
        self.before = json.loads(app_output.read_text())
        # The same event handlers used by GTK pointer events map fitted pixels
        # back to the compositor's logical screen coordinates.
        left, top, width, height = content_rectangle(
            self.picture.get_width(), self.picture.get_height(), self.screen)
        x, y = self.before["duration_target"]
        assert self._motion(None, left + x / self.capture.logical_width * width,
                            top + y / self.capture.logical_height * height)
        GLib.timeout_add(150, self.press)
        return False

    def press(self):
        self.capture.button(272, True)
        GLib.timeout_add(100, self.release)
        return False

    def release(self):
        self.capture.button(272, False)
        # Changing host allocations can move focus. Let the received input
        # finish its GTK frame before exercising the viewer's zoom controls.
        GLib.timeout_add(300, self.zoom)
        return False

    def zoom(self):
        self.pixel_view.set_active(True)
        GLib.timeout_add(400, self.inspect_pixels)
        return False

    def inspect_pixels(self):
        self.after = json.loads(app_output.read_text())
        self.pixel_size = [self.picture.get_width(), self.picture.get_height()]
        self.host_scale = self.window.get_surface().get_scale()
        # Return to fit and resize the actual host window. The private monitor
        # and the rendered app must retain their selected dimensions.
        self.pixel_view.set_active(False)
        self.window.set_default_size(800, 650)
        # Keyboard navigation must use the same focused production controls.
        self._key_pressed(None, 0, 116, 0)  # XKB Down -> evdev KEY_DOWN
        self._key_released(None, 0, 116, 0)
        GLib.timeout_add(100, self.activate_focused)
        GLib.timeout_add(500, self.finish)
        return False

    def activate_focused(self):
        self._key_pressed(None, 0, 65, 0)  # XKB Space -> evdev KEY_SPACE
        self._key_released(None, 0, 65, 0)
        return False

    def finish(self):
        state = self.capture.call("org.gnome.Mutter.DisplayConfig",
                                  "/org/gnome/Mutter/DisplayConfig",
                                  "org.gnome.Mutter.DisplayConfig", "GetCurrentState")
        output.write_text(json.dumps({
            "source": [self.capture.paintable.get_intrinsic_width(),
                       self.capture.paintable.get_intrinsic_height()],
            "pixel_view": self.pixel_size, "host_scale": self.host_scale,
            "before": self.before, "after": self.after,
            "after_keyboard": json.loads(app_output.read_text()),
            "monitors": len(state[1]), "logical_monitors": len(state[2]),
            "mapped": self.window.get_mapped(),
        }))
        return False


app = Probe()
raise SystemExit(run(app))
