"""Minimal stable GTK automation identity publication shared by owned UIs."""

from __future__ import annotations

import re


_AUTOMATION_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_PUBLISHED = {}


class _PublishedIdentity:
    """Keep identity for the native widget lifetime without retaining it."""

    def __init__(self, widget, identity):
        self.key = hash(widget)
        self.identity = identity
        self.target = widget.weak_ref(self.release)

    def release(self, *_args):
        if _PUBLISHED.get(self.key) is self:
            del _PUBLISHED[self.key]


def automation_id(widget):
    """Return only an explicitly published application identity.

    GTK templates also assign Buildable IDs, often repeated in separate rows.
    Those toolkit implementation names are not application API elements.
    """
    record = _PUBLISHED.get(hash(widget))
    return (record.identity if record is not None and record.target() == widget
            else "")


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
    record = _PUBLISHED.get(hash(widget))
    if record is not None and record.target() == widget:
        record.identity = automation_id
    else:
        _PUBLISHED[hash(widget)] = _PublishedIdentity(widget, automation_id)
    return widget


def identified_window_controls(automation_id: str):
    """Create GTK-owned title buttons behind one stable public identity."""
    from gi.repository import Gtk
    return set_automation_id(
        Gtk.WindowControls(side=Gtk.PackType.END), automation_id,
    )


def add_identified_window_controls(header, automation_id: str):
    """Replace a header bar's implicit buttons with one identified owner."""
    if hasattr(header, "set_show_end_title_buttons"):
        header.set_show_end_title_buttons(False)
    else:
        header.set_show_title_buttons(False)
    controls = identified_window_controls(automation_id)
    header.pack_end(controls)
    return controls
