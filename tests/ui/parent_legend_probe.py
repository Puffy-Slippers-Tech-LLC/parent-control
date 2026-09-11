"""Record the production legend's settled layout without changing it."""

import json
from pathlib import Path

from gi.repository import GLib, Gtk


def _descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from _descendants(child)
        child = child.get_next_sibling()


def attach(application, directory):
    window = application.get_active_window()
    card = next(widget for widget in _descendants(window)
                if widget.has_css_class("policy-legend"))
    revealer = card.get_last_child()

    def revealed(*_args):
        if revealer.get_child_revealed():
            GLib.idle_add(capture, window, card, Path(directory))

    revealer.connect("notify::child-revealed", revealed)


def capture(window, card, directory):
    records = []
    for widget in _descendants(card):
        valid, bounds = widget.compute_bounds(card)
        assert valid
        records.append({
            "type": type(widget).__name__,
            "classes": widget.get_css_classes(),
            "bounds": [bounds.get_x(), bounds.get_y(),
                       bounds.get_width(), bounds.get_height()],
        })
    snapshot = Gtk.Snapshot.new()
    Gtk.WidgetPaintable.new(card).snapshot(
        snapshot, card.get_width(), card.get_height(),
    )
    texture = window.get_renderer().render_texture(snapshot.to_node(), None)
    texture.save_to_png(str(directory / "legend.png"))
    (directory / "layout.json").write_text(json.dumps({
        "window": [window.get_width(), window.get_height()],
        "widgets": records,
    }, indent=2))
    return GLib.SOURCE_REMOVE
