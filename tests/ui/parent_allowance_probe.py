"""Record real popup placement and pixels on the private test compositor."""

import json
from itertools import count
from pathlib import Path

from gi.repository import GLib, Graphene, Gtk


def attach(application, directory):
    window = application.get_active_window()
    popover = window._daily_limit.get_popover()
    captures = count()
    popover.connect("map", lambda *_: GLib.timeout_add(
        250, capture, window, popover, Path(directory), next(captures),
    ))


def capture(window, popover, directory, index):
    surface = popover.get_surface()
    if not surface.get_mapped():
        return GLib.SOURCE_REMOVE
    valid, button = window._daily_limit.compute_bounds(window)
    assert valid
    valid, menu = popover.get_child().compute_bounds(popover)
    assert valid
    window_x, window_y = window.get_surface_transform()
    popup_x, popup_y = popover.get_surface_transform()
    offset_x = surface.get_position_x() + popup_x - window_x
    offset_y = surface.get_position_y() + popup_y - window_y
    record = {
        "window": [window.get_width(), window.get_height()],
        "button": [button.get_x(), button.get_y(),
                   button.get_width(), button.get_height()],
        "popup": [surface.get_position_x(), surface.get_position_y(),
                  surface.get_width(), surface.get_height()],
        "menu": [offset_x + menu.get_x(), offset_y + menu.get_y(),
                 menu.get_width(), menu.get_height()],
        "rect_anchor": surface.get_rect_anchor().value_nick,
        "surface_anchor": surface.get_surface_anchor().value_nick,
    }
    # Compose the two native surfaces in parent-surface coordinates so the
    # evidence includes the arrow's relationship to the triggering button.
    snapshot = Gtk.Snapshot.new()
    Gtk.WidgetPaintable.new(window).snapshot(
        snapshot, window.get_width(), window.get_height(),
    )
    snapshot.save()
    snapshot.translate(Graphene.Point().init(offset_x, offset_y))
    Gtk.WidgetPaintable.new(popover).snapshot(
        snapshot, popover.get_width(), popover.get_height(),
    )
    snapshot.restore()
    node = snapshot.to_node()
    assert node is not None
    texture = window.get_renderer().render_texture(
        node, Graphene.Rect().init(0, 0, window.get_width(), window.get_height()),
    )
    assert texture.save_to_png(str(directory / f"allowance-{index}.png"))
    (directory / f"layout-{index}.json").write_text(json.dumps(record, indent=2))
    return GLib.SOURCE_REMOVE
