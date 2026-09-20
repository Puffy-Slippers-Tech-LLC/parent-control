"""Minimal stable GTK automation identity publication shared by owned UIs."""

from __future__ import annotations

import re


_AUTOMATION_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")


def set_automation_id(widget, automation_id: str):
    """Publish one lowercase semantic ID as GTK's public Buildable identity."""
    if type(automation_id) is not str or not _AUTOMATION_ID.fullmatch(automation_id):
        raise ValueError("automation_id must be a lowercase hyphenated identifier")
    widget.set_name(automation_id)
    # Import lazily so non-GUI unit tests can import helpers without selecting
    # a GTK version. Callers establish their supported GTK version first.
    from gi.repository import Gtk
    builder = Gtk.Builder()
    builder.expose_object(automation_id, widget)
    return widget
