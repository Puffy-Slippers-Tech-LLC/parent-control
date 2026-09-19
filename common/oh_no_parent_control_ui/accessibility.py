"""Human-readable accessibility metadata shared by GTK front ends."""

from __future__ import annotations

import re

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk


_AUTOMATION_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")


def set_automation_id(widget, automation_id: str):
    """Assign a stable GTK widget identity for public GUI automation.

    GTK 4.22 exposes the Buildable ID as AT-SPI AccessibleId. A CSS name
    alone does not reach that public interface. Expose the existing object
    through a temporary Builder; the ID belongs to the object and survives
    the Builder. Labels and descriptions remain human-readable.

    Older GTK versions retain the Buildable ID but cannot publish it through
    AT-SPI. Automation must report that missing capability, never fall back
    to names, roles or geometry.
    """
    if type(automation_id) is not str or not _AUTOMATION_ID.fullmatch(automation_id):
        raise ValueError("automation_id must be a lowercase hyphenated identifier")
    widget.set_name(automation_id)
    builder = Gtk.Builder()
    builder.expose_object(automation_id, widget)
    if isinstance(widget, Gtk.MenuButton):
        # GtkMenuButton's AT-SPI Action interface exposes the widget's action
        # groups, not its activate signal. Publish an explicit native popup
        # action so assistive clients need not target its internal toggle.
        # Follow the GObject lifetime, not a temporary Python wrapper: a
        # menu button may remain parented after its local wrapper is released.
        target = widget.weak_ref()
        action = Gio.SimpleAction.new("popup", None)

        def popup(_action, _parameter):
            button = target()
            if button is not None and button.is_sensitive():
                button.popup()

        action.connect("activate", popup)
        group = Gio.SimpleActionGroup()
        group.add_action(action)
        widget.insert_action_group("menu", group)
    elif isinstance(widget, Gtk.CheckButton):
        # GtkCheckButton is not a GtkButton subclass. GTK therefore publishes
        # inherited widget actions instead of its activate signal through
        # AT-SPI. Add one native action that retains GTK's checkbox and radio
        # activation semantics.
        target = widget.weak_ref()
        action = Gio.SimpleAction.new("toggle", None)

        def toggle(_action, _parameter):
            button = target()
            if button is not None and button.is_sensitive():
                button.grab_focus()
                button.activate()

        action.connect("activate", toggle)
        group = Gio.SimpleActionGroup()
        group.add_action(action)
        widget.insert_action_group("check", group)
    return widget


def describe_control(widget, label: str, description: str, *, automation_id=None) -> None:
    """Give an interactive widget human-readable AT-SPI metadata.

    Labels describe the control's purpose to assistive technology users.  They
    are separate from the explicit automation identity used by UI tests.
    """

    widget.update_property(
        [Gtk.AccessibleProperty.LABEL, Gtk.AccessibleProperty.DESCRIPTION],
        [label, description],
    )
    if automation_id is not None:
        set_automation_id(widget, automation_id)


def add_dialog_button(dialog, label: str, response_id, automation_id: str, *,
                      description: str | None = None, css_class: str | None = None):
    """Add one ID-addressable Gtk.Dialog response with accessible metadata."""
    button = dialog.add_button(label, response_id)
    describe_control(
        button,
        label,
        description or label,
        automation_id=automation_id,
    )
    if css_class is not None:
        button.add_css_class(css_class)
    return button
