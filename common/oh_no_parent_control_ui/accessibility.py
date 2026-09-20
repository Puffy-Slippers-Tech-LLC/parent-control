"""Human-readable accessibility metadata shared by GTK front ends."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from common.oh_no_parent_control_ui.gtk_automation import (
    add_identified_window_controls,
    set_automation_id as _set_buildable_automation_id,
)


def _publish_effective_sensitivity(widget, *_args):
    # GTK's own DISABLED publication follows set_sensitive(), which is local
    # to the widget. Inherited insensitivity changes state flags instead.
    # Publish the actual interaction state on each identified control so
    # assistive clients need not infer it from anonymous toolkit ancestors.
    widget.update_state([Gtk.AccessibleState.DISABLED], [not widget.is_sensitive()])


def _update_controlled_surfaces(parent):
    references = getattr(parent, "_public_controlled_surfaces", [])
    children = [reference() for reference in references if reference() is not None]
    parent._public_controlled_surfaces = [child.weak_ref() for child in children]
    if children:
        # GTK publishes the inverse CONTROLLED_BY relation automatically.
        # Reference-list relations need GTK's boxed list in language bindings;
        # an ordinary Python list becomes a PyObject GValue, not a GTK list.
        parent.update_relation([Gtk.AccessibleRelation.CONTROLS],
                               [Gtk.AccessibleList.new_from_list(children)])
    else:
        parent.reset_relation(Gtk.AccessibleRelation.CONTROLS)


def _unpublish_surface_owner(widget):
    reference = getattr(widget, "_public_controller", None)
    parent = reference() if reference is not None else None
    if parent is not None:
        parent._public_controlled_surfaces = [
            reference for reference in getattr(parent, "_public_controlled_surfaces", [])
            if reference() is not None and reference() != widget]
        _update_controlled_surfaces(parent)
    widget._public_controller = None


def _publish_surface_owner(widget):
    identity = Gtk.Buildable.get_buildable_id(widget) or ""
    if not identity.endswith(("-dialog", "-window")):
        return
    parent = (widget.get_transient_for() if isinstance(widget, Gtk.Window)
              else widget.get_parent())
    while parent is not None:
        if (Gtk.Buildable.get_buildable_id(parent) or "").endswith(("-dialog", "-window")):
            _unpublish_surface_owner(widget)
            parent._public_controlled_surfaces = [
                *getattr(parent, "_public_controlled_surfaces", []), widget.weak_ref()]
            widget._public_controller = parent.weak_ref()
            _update_controlled_surfaces(parent)
            return
        if isinstance(parent, Gtk.Window):
            parent = parent.get_transient_for()
        else:
            parent = parent.get_parent()


def _publish_focus(widget):
    """Expose native focus on the owning surface's AT-SPI Action interface.

    Entry and Button have specialized Action interfaces that hide inserted
    groups. The surface action names address Buildable IDs, never child order.
    Native GTK focus also performs the toolkit's normal scrolling into view.
    """
    root = widget.get_root()
    if not isinstance(root, Gtk.Window) or widget is root:
        return
    # Adw.Dialog can be hosted inside an internal Gtk.Window. Publish on the
    # identified dialog itself, not that anonymous toolkit hosting window.
    surface = widget.get_parent()
    while surface is not None:
        surface_id = Gtk.Buildable.get_buildable_id(surface) or ""
        if surface_id.endswith(("-dialog", "-window")):
            break
        surface = surface.get_parent()
    if surface is None:
        return
    identity = Gtk.Buildable.get_buildable_id(widget)
    group = getattr(surface, "_public_focus_actions", None)
    if group is None:
        group = Gio.SimpleActionGroup()
        surface._public_focus_actions = group
        surface.insert_action_group("focus", group)
    target = widget.weak_ref()
    owner = root.weak_ref()
    containing_surface = surface.weak_ref()
    action = Gio.SimpleAction.new(identity, None)

    def focus(_action, _parameter):
        control, window, container = target(), owner(), containing_surface()
        if (control is not None and window is not None and container is not None
                and control.is_ancestor(container)
                and control.get_root() is window
                and Gtk.Buildable.get_buildable_id(control) == identity
                and control.get_mapped() and control.is_visible()
                and control.is_sensitive() and window.is_active()):
            control.grab_focus()

    action.connect("activate", focus)
    group.add_action(action)


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
    _set_buildable_automation_id(widget, automation_id)
    if not getattr(widget, "_public_focus_connected", False):
        widget._public_focus_connected = True
        widget.connect("map", _publish_focus)
        widget.connect("map", _publish_surface_owner)
        widget.connect("unmap", _unpublish_surface_owner)
        widget.connect("state-flags-changed", _publish_effective_sensitivity)
        # A local change under an already disabled parent need not change the
        # effective state flags, but GTK still overwrites its DISABLED value.
        widget.connect("notify::sensitive", _publish_effective_sensitivity)
    _publish_effective_sensitivity(widget)
    if widget.get_mapped():
        _publish_focus(widget)
        _publish_surface_owner(widget)
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
    elif isinstance(widget, Gtk.ListBoxRow):
        # List rows expose inherited widget actions, not necessarily their
        # native activation signal. Publish that documented keybinding action
        # so AT-SPI clients can select an ID-addressed row without coordinates
        # or relying on the provider's unsupported row focus operation.
        target = widget.weak_ref()
        action = Gio.SimpleAction.new("activate", None)

        def activate(_action, _parameter):
            row = target()
            if row is not None and row.is_sensitive():
                row.emit("activate")

        action.connect("activate", activate)
        group = Gio.SimpleActionGroup()
        group.add_action(action)
        widget.insert_action_group("row", group)
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
