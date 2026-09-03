"""Human-readable accessibility metadata shared by GTK front ends."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def describe_control(widget, label: str, description: str) -> None:
    """Give an interactive widget a stable, useful AT-SPI identity.

    Labels describe the control's purpose to assistive technology users.  They
    also let semantic UI tests locate controls without relying on CSS classes,
    widget order, coordinates, or hidden test-only identifiers.
    """

    widget.update_property(
        [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION],
        [label, description],
    )
