"""Observe the real fullscreen surface and exercise the screen dialog widgets."""

import json
import os
from pathlib import Path

from kiosk.oh_no_parent_control_kiosk.main import Application, GLib, Graphene, Gtk, RequestWindow
from kiosk.oh_no_parent_control_kiosk.preview_screen import show_screen_dialog


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from descendants(child)
        child = child.get_next_sibling()


def inspect(window):
    output = Path(os.environ["ONPC_SCREEN_EVIDENCE"])
    record = {
        "width": window.get_width(), "height": window.get_height(),
        "scale": window.get_surface().get_scale(), "fullscreen": window.is_fullscreen(),
        "viewport": [window._request_surface.get_width(), window._request_surface.get_height()],
    }
    show_screen_dialog(window)

    def check_dialog():
        dialog = window.get_visible_dialog()
        snapshot = Gtk.Snapshot.new()
        window.snapshot_child(window.get_child(), snapshot)
        texture = window.get_renderer().render_texture(snapshot.to_node(), Graphene.Rect().init(
            0, 0, window.get_width(), window.get_height(),
        ))
        assert texture.save_to_png(str(output.with_suffix(".png")))
        print(f"Screen dialog screenshot: {output.with_suffix('.png')}", flush=True)
        widgets = list(descendants(dialog))
        resolutions = next(widget for widget in widgets if isinstance(widget, Gtk.ListBox))
        custom = resolutions.get_last_child()
        resolutions.select_row(custom)
        entries = [widget for widget in widgets if isinstance(widget, Gtk.Entry)]
        assert len(entries) == 2
        entries[0].set_text("invalid")
        save = next(widget for widget in widgets if isinstance(widget, Gtk.Button)
                    and widget.get_label() == "Save")
        save.emit("clicked")
        record["invalid_error"] = any(
            isinstance(widget, Gtk.Label) and widget.get_visible()
            and widget.get_text() == "Enter a whole number for both width and height."
            for widget in widgets
        )
        record["save_still_enabled"] = save.get_sensitive()
        if os.environ.get("ONPC_SCREEN_CHANGE") == "1" and window.get_width() == 1920:
            # First Save asks Mutter for an unsupported combination. Verify the
            # error returns to the old dialog, then save a valid custom screen.
            entries[0].set_text("480")
            entries[1].set_text("480")
            scale = next(widget for widget in widgets if isinstance(widget, Gtk.DropDown))
            scale.set_selected(12)  # 400%
            save.emit("clicked")

            def retry():
                if not save.get_sensitive():
                    return GLib.SOURCE_CONTINUE
                assert any(isinstance(widget, Gtk.Label) and "This resolution supports" in widget.get_text()
                           for widget in widgets)
                entries[0].set_text("2560")
                entries[1].set_text("1600")
                scale.set_selected(1)  # 125%
                save.emit("clicked")
                return GLib.SOURCE_REMOVE

            GLib.timeout_add(100, retry)
            return GLib.SOURCE_REMOVE
        dialog.close()
        output.write_text(json.dumps(record), encoding="utf-8")
        return GLib.SOURCE_REMOVE

    GLib.timeout_add(300, check_dialog)
    return GLib.SOURCE_REMOVE


def window_factory(application, **kwargs):
    window = RequestWindow(application, **kwargs)
    window.connect("map", lambda *_: GLib.timeout_add(1000, inspect, window))
    return window


Application(preview=True, child_overlay=os.environ.get("ONPC_SCREEN_CHILD") == "1",
            window_factory=window_factory).run([])
