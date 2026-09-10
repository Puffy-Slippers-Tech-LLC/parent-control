"""Measure and render real request widgets on the private test compositor."""

from __future__ import annotations

import json
import os
from pathlib import Path
import traceback

from gi.repository import GLib

from kiosk.oh_no_parent_control_kiosk.main import (
    Application, Graphene, Gtk, RequestWindow, _gateway_inner_corners,
)


directory = Path(os.environ["ONPC_REQUEST_LAYOUT_DIRECTORY"])
overlay = os.environ.get("ONPC_REQUEST_LAYOUT_OVERLAY") == "1"
failures = []
sizes = ((800, 600), (1024, 768), (1366, 768), (1920, 1080),
         (1918, 1443), (1517, 947), (2560, 1440), (3840, 2160),
         (768, 1024), (480, 800), (3840, 1080), (1920, 1080),
         (1536, 960), (1920, 1200))


def bounds(widget, ancestor):
    valid, rectangle = widget.compute_bounds(ancestor)
    assert valid
    return [rectangle.get_x(), rectangle.get_y(),
            rectangle.get_width(), rectangle.get_height()]


def inspect_layout(window):
    try:
        content = window.get_content()
        form = window._request_content
        viewport = window._request_surface._viewport
        records = []
        for width, height in sizes:
            for expanded, custom in ((False, False), (False, True), (True, True)):
                form._approvers._set_expanded(expanded)
                form._custom_row.set_visible(custom)
                content.allocate(width, height, -1, None)
                adjustment = viewport.get_vadjustment()
                adjustment.set_value(0)
                content.allocate(width, height, -1, None)
                record = {
                    "size": [width, height], "expanded": expanded, "custom": custom,
                    "monitor_scale": window.get_scale_factor(),
                    "surface_scale": window.get_surface().get_scale(),
                    "viewport": bounds(viewport, content),
                    "viewport_allocation": [viewport.get_width(), viewport.get_height()],
                    "gateway_opening": _gateway_inner_corners(width, height),
                    "mute_button": bounds(window._mute_button, content),
                    "board_width": form.get_allocated_width(),
                    "board_minimum": form.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
                    - form.get_margin_start() - form.get_margin_end(),
                    "board_margin": form.get_margin_start() + form.get_margin_end(),
                    "scroll_upper": adjustment.get_upper(),
                    "scroll_page": adjustment.get_page_size(),
                    "status_font": form._status.get_pango_context()
                    .get_font_description().get_size() / 1024,
                    "durations": [bounds(button, form)
                                  for button in form._duration_buttons],
                    "sections": [],
                    "minimums": {
                        name: widget.measure(Gtk.Orientation.HORIZONTAL, -1)[0]
                        for name, widget in (
                            ("choices", form._choices), ("custom", form._custom_row),
                            ("filter", form._filter_row), ("accounts", form._accounts),
                        )
                    },
                }
                section = form.get_first_child()
                while section:
                    record["sections"].append({
                        "classes": section.get_css_classes(),
                        "bounds": bounds(section, form),
                        "minimum": section.measure(Gtk.Orientation.HORIZONTAL, -1)[0],
                    })
                    section = section.get_next_sibling()
                button = form._duration_buttons[0]
                valid, point = button.compute_point(content, Graphene.Point().init(
                    button.get_width() / 2, button.get_height() / 2,
                ))
                assert valid
                picked = content.pick(point.x, point.y, Gtk.PickFlags.DEFAULT)
                while picked is not None and picked is not button:
                    picked = picked.get_parent()
                record["duration_pick"] = picked is button
                valid, point = window._mute_button.compute_point(
                    content, Graphene.Point().init(33, 33),
                )
                assert valid
                picked = content.pick(point.x, point.y, Gtk.PickFlags.DEFAULT)
                while picked is not None and picked is not window._mute_button:
                    picked = picked.get_parent()
                record["mute_pick"] = picked is window._mute_button
                snapshot = Gtk.Snapshot.new()
                content.get_parent().snapshot_child(content, snapshot)
                node = snapshot.to_node()
                assert node is not None
                texture = window.get_renderer().render_texture(
                    node, Graphene.Rect().init(0, 0, width, height),
                )
                state = "expanded" if expanded else "custom" if custom else "normal"
                name = f"request-{width}x{height}-{state}.png"
                assert texture.save_to_png(str(directory / name))
                if (width, height) == (1536, 960):
                    physical = Gtk.Snapshot.new()
                    physical.scale(1.25, 1.25)
                    physical.append_node(node)
                    texture = window.get_renderer().render_texture(
                        physical.to_node(), Graphene.Rect().init(0, 0, 1920, 1200),
                    )
                    assert texture.save_to_png(str(directory / f"laptop-{name}"))
                adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
                content.allocate(width, height, -1, None)
                record["footer_after_scroll"] = bounds(form._status, viewport)
                if adjustment.get_upper() > adjustment.get_page_size() + 1:
                    scrollbar = window._request_surface._scrollbar
                    record["scrollbar"] = bounds(scrollbar, content)
                    valid, point = scrollbar.compute_point(
                        content, Graphene.Point().init(
                            scrollbar.get_width() / 2, scrollbar.get_height() / 2,
                        ),
                    )
                    assert valid
                    picked = content.pick(point.x, point.y, Gtk.PickFlags.DEFAULT)
                    while picked is not None and picked is not scrollbar:
                        picked = picked.get_parent()
                    record["scrollbar_pick"] = picked is scrollbar
                records.append(record)
        (directory / "layout.json").write_text(json.dumps(records, indent=2))
        print(f"Request layout evidence: {directory}", flush=True)
    except Exception:
        traceback.print_exc()
        failures.append(True)
    finally:
        application = window.get_application()
        window.destroy()
        application.quit()
    return GLib.SOURCE_REMOVE


def window_factory(application, **kwargs):
    window = RequestWindow(application, **kwargs)
    window.connect("map", lambda *_: GLib.timeout_add(500, inspect_layout, window))
    return window


app = Application(preview=True, child_overlay=overlay, window_factory=window_factory)
result = app.run([])
raise SystemExit(1 if failures else result)
