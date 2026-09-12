"""Capture actual feedback spinner frames during the delayed collection fixture."""

import os
from pathlib import Path

from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.feedback import FeedbackDialog


class ObservedFeedbackDialog(FeedbackDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_settings().set_property(
            "gtk-enable-animations", os.environ["ONPC_FEEDBACK_ANIMATIONS"] == "true",
        )
        self._collection_spinner.connect("map", self._observe_spinner)

    def _observe_spinner(self, spinner):
        directory = Path(os.environ["ONPC_FEEDBACK_SPINNER_DIRECTORY"])
        paintable = Gtk.WidgetPaintable.new(spinner)
        frames = 0

        def capture():
            nonlocal frames
            if not spinner.get_mapped():
                return GLib.SOURCE_REMOVE
            snapshot = Gtk.Snapshot.new()
            paintable.snapshot(snapshot, spinner.get_width(), spinner.get_height())
            node = snapshot.to_node()
            if node is not None:
                texture = self.get_renderer().render_texture(node, None)
                texture.save_to_png(str(directory / f"spinner-{frames}.png"))
                frames += 1
            return GLib.SOURCE_CONTINUE if frames < 8 else GLib.SOURCE_REMOVE

        GLib.timeout_add(150, capture)
