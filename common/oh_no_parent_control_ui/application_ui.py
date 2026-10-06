"""Bounded, ID-addressed public operations on the running application's UI.

This service never calls the broker or interprets caller-supplied code. Bindings
operate the same widgets and signals as interactive users. Values are protocol
values, independent of translated labels, focus, geometry and popup state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import re
import threading


INTERFACE = "com.puffyslippers.OhNoParentControl.ApplicationUI1"
INTROSPECTION_XML = f"""<node><interface name="{INTERFACE}">
  <method name="ListSurfaces"><arg type="s" direction="out"/></method>
  <method name="Call">
    <arg name="surface_id" type="s" direction="in"/>
    <arg name="element_id" type="s" direction="in"/>
    <arg name="operation" type="s" direction="in"/>
    <arg name="arguments_json" type="s" direction="in"/>
    <arg name="result_json" type="s" direction="out"/>
  </method>
</interface></node>"""

_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_OPERATIONS = frozenset({"getElementById", "getValue", "setValue", "getText",
                         "setText", "activate", "getChoices", "close"})
_INPUTS = frozenset({"setValue", "setText", "activate", "close"})
_MAX_BYTES = 256 * 1024
_MAX_WIDGETS = 100000
_MAX_PENDING = 32
_TIMEOUT_SECONDS = 10


class UIError(ValueError):
    """A fixed public error category, without user data in diagnostics."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class _Binding:
    callbacks: dict = field(default_factory=dict)
    aliases: tuple = ()
    dispatcher: object = None
    operations: frozenset = frozenset()


@dataclass
class _Request:
    source: int
    invocation: object
    cancellable: object
    input_dispatched: bool = False


def bind_ui(widget, *, get_value=None, set_value=None, get_text=None,
            set_text=None, activate=None, choices=None, aliases=(),
            dispatcher=None, operations=()):
    """Register semantic widget operations; return the widget for composition.

    Getters and activate take no arguments. Setters take their typed value.
    ``choices`` is a no-argument getter or a finite JSON-compatible sequence.
    Explicit callbacks override generic GTK operations. Aliases address the same
    widget; they need no Builder ID and may be registered before its primary ID.

    A dispatcher handles virtual alias elements, such as controls in an owned
    WebKit document. It receives ``(operation, arguments, complete)`` with an
    added ``element_id`` argument. It must validate the actual document target,
    including hidden/disabled state, and call ``complete(result, error=None)``
    exactly once. Only the declared operations are offered. The host widget's
    ownership and availability are checked separately by this service.
    """
    aliases = tuple(aliases)
    if (len(aliases) > 128 or len(set(aliases)) != len(aliases)
            or any(type(identity) is not str or len(identity) > 255 or not _ID.fullmatch(identity)
                   for identity in aliases)):
        raise ValueError("Invalid UI aliases")
    operations = frozenset(operations)
    if not operations <= _OPERATIONS or (operations and dispatcher is None):
        raise ValueError("Invalid UI dispatcher operations")
    callbacks = {"getValue": get_value, "setValue": set_value,
                 "getText": get_text, "setText": set_text,
                 "activate": activate}
    if any(callback is not None and not callable(callback)
           for callback in callbacks.values()):
        raise ValueError("UI operations must be callable")
    if dispatcher is not None and not callable(dispatcher):
        raise ValueError("UI dispatcher must be callable")
    if choices is not None:
        if not callable(choices):
            _encode(choices)
            if not isinstance(choices, (tuple, list)):
                raise ValueError("UI choices must be a sequence")
            fixed_choices = tuple(choices)
            choices = lambda: fixed_choices
        callbacks["getChoices"] = choices
    widget._application_ui_binding = _Binding(
        {key: value for key, value in callbacks.items() if value is not None},
        aliases, dispatcher, operations,
    )
    return widget


def _validate_json(value, depth=0, budget=None):
    if budget is None:
        budget = [65536]
    budget[0] -= 1
    if budget[0] < 0 or depth > 16:
        raise UIError("InvalidArgument")
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise UIError("InvalidArgument")
        return
    if type(value) is str:
        if len(value.encode("utf-8")) > _MAX_BYTES:
            raise UIError("InvalidArgument")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json(item, depth + 1, budget)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise UIError("InvalidArgument")
            _validate_json(key, depth + 1, budget)
            _validate_json(item, depth + 1, budget)
        return
    raise UIError("InvalidArgument")


def _encode(value):
    _validate_json(value)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_BYTES:
        raise UIError("InvalidArgument")
    return encoded


def _decode(encoded, *, require_dict=True):
    if type(encoded) is not str or len(encoded.encode("utf-8")) > _MAX_BYTES:
        raise UIError("InvalidArgument")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise UIError("InvalidArgument")
            result[key] = value
        return result

    try:
        value = json.loads(encoded, object_pairs_hook=pairs)
        _validate_json(value)
    except (ValueError, TypeError, RecursionError) as error:
        raise UIError("InvalidArgument") from error
    if require_dict and type(value) is not dict:
        raise UIError("InvalidArgument")
    return value


def _gtk():
    # Identity helpers are also copied to standalone viewers. Keep this module
    # optional there, and defer GTK imports until an application uses the API.
    from gi.repository import Gtk
    return Gtk


def _identity(widget):
    from .gtk_automation import automation_id
    return automation_id(widget)


def _binding(widget):
    return getattr(widget, "_application_ui_binding", _Binding())


def _visible(widget):
    # Mapped state, clipping and focus are deliberately not recipient guards.
    # Child visibility does distinguish an inactive Stack page from scrolling.
    Gtk = _gtk()
    current = widget
    while current is not None:
        if not current.get_visible():
            return False
        parent = current.get_parent()
        if isinstance(parent, Gtk.Revealer) and not parent.get_reveal_child():
            return False
        # child-visible is also used by toolkit culling. Gtk.Stack and
        # Adw.ViewStack both expose the actual active page through this public
        # method; viewport/layout flags do not represent hidden app state.
        if (parent is not None and hasattr(parent, "get_visible_child")
                and parent.get_visible_child() != current):
            return False
        current = parent
    return True


def _children(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def _walk(root):
    pending = [root]
    count = 0
    while pending:
        widget = pending.pop()
        count += 1
        if count > _MAX_WIDGETS:
            raise UIError("Unavailable")
        yield widget
        pending.extend(reversed(tuple(_children(widget))))


def _is_surface(widget):
    Gtk = _gtk()
    if isinstance(widget, Gtk.Window):
        return True
    # Adw.Dialog can be hosted within an anonymous native Gtk.Window. Avoid an
    # extra typelib dependency by checking the public GType inheritance chain.
    from gi.repository import GObject
    kind = widget.__gtype__
    # All GTK widgets derive from GObject. PyGObject's type_parent raises at
    # that root rather than returning an invalid (false) GType.
    while kind != GObject.TYPE_OBJECT:
        if GObject.type_name(kind) == "AdwDialog":
            return True
        kind = GObject.type_parent(kind)
    return False


def _strict_bool(value):
    if type(value) is not bool:
        raise UIError("InvalidArgument")
    return value


def _strict_text(value):
    if type(value) is not str or "\x00" in value:
        raise UIError("InvalidArgument")
    return value


def _number(widget, value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise UIError("InvalidArgument")
    adjustment = widget.get_adjustment()
    maximum = adjustment.get_upper()
    if isinstance(widget, _gtk().Range):
        maximum -= adjustment.get_page_size()
    if value < adjustment.get_lower() or value > maximum:
        raise UIError("InvalidArgument")
    return value


def _toggle_button(widget, value):
    desired = _strict_bool(value)
    if widget.get_active() != desired:
        # GtkToggleButton's native clicked handler updates active state before
        # application clicked handlers. set_active alone misses those handlers.
        widget.emit("clicked")
        if widget.get_active() != desired:
            raise UIError("Unavailable")


def _check_button(widget, value):
    desired = _strict_bool(value)
    if widget.get_active() != desired:
        # set_active(False) can clear a grouped radio that a customer cannot
        # deselect. Its native action preserves radio-group constraints.
        widget.emit("activate")
        if widget.get_active() != desired:
            raise UIError("Unavailable")


def _button_text(widget):
    label = widget.get_label()
    if label is not None:
        return label
    Gtk = _gtk()
    return " ".join(child.get_text() for child in _walk(widget)
                    if isinstance(child, Gtk.Label) and _visible(child))


def _close_surface(widget):
    if hasattr(widget, "get_can_close") and not widget.get_can_close():
        raise UIError("Unavailable")
    # These public methods preserve close-request and Adw can-close policy.
    if widget.close() is False:
        raise UIError("Unavailable")


def _generic(widget):
    """Use supported GTK operations and their normal change/activation signals."""
    Gtk = _gtk()
    result = {}
    if isinstance(widget, Gtk.ToggleButton):
        result["getValue"] = widget.get_active
        result["setValue"] = lambda value: _toggle_button(widget, value)
    elif isinstance(widget, Gtk.CheckButton):
        result["getValue"] = widget.get_active
        result["setValue"] = lambda value: _check_button(widget, value)
    elif isinstance(widget, Gtk.Switch):
        result["getValue"] = widget.get_active
        result["setValue"] = lambda value: widget.set_active(_strict_bool(value))
    elif isinstance(widget, (Gtk.SpinButton, Gtk.Range)):
        result["getValue"] = widget.get_value
        result["setValue"] = lambda value: widget.set_value(_number(widget, value))
    elif isinstance(widget, Gtk.Expander):
        result["getValue"] = widget.get_expanded
        result["setValue"] = lambda value: widget.set_expanded(_strict_bool(value))
    elif isinstance(widget, Gtk.Editable):
        result["getValue"] = widget.get_text
        result["setValue"] = lambda value: widget.set_text(_strict_text(value))
    if isinstance(widget, Gtk.Editable):
        result["getText"] = widget.get_text
        result["setText"] = lambda text: widget.set_text(_strict_text(text))
        if not widget.get_editable():
            result.pop("setText", None)
            result.pop("setValue", None)
    elif isinstance(widget, Gtk.TextView):
        buffer = widget.get_buffer()
        result["getText"] = lambda: buffer.get_text(*buffer.get_bounds(), True)
        result["getValue"] = result["getText"]
        if widget.get_editable():
            result["setText"] = lambda text: buffer.set_text(_strict_text(text))
            result["setValue"] = result["setText"]
    elif isinstance(widget, Gtk.Label):
        result["getText"] = widget.get_text
    elif isinstance(widget, (Gtk.Button, Gtk.MenuButton)):
        result["getText"] = lambda: _button_text(widget)
    elif hasattr(widget, "get_title") and hasattr(widget, "get_subtitle"):
        # Adw.ActionRow exposes both logical strings as public properties.
        result["getText"] = lambda: "\n".join(
            text for text in (widget.get_title(), widget.get_subtitle()) if text)
    elif isinstance(widget, Gtk.Window):
        result["getText"] = lambda: widget.get_title() or ""
    elif isinstance(widget, Gtk.Widget):
        # Structural controls communicate their logical content through real
        # child labels. Consumers need no anonymous accessibility descendants.
        result["getText"] = lambda: "\n".join(
            child.get_text() for child in _walk(widget)
            if isinstance(child, Gtk.Label) and _visible(child))
    if isinstance(widget, Gtk.MenuButton):
        result["activate"] = widget.popup
    elif isinstance(widget, Gtk.Switch):
        result["activate"] = lambda: widget.set_active(not widget.get_active())
    elif isinstance(widget, Gtk.ListBoxRow):
        if widget.get_activatable():
            result["activate"] = lambda: widget.emit("activate")
    elif isinstance(widget, Gtk.Button):
        # Gtk.Widget.activate() can defer clicked until its animation ends.
        # The native signal runs the GTK class closure and user handlers now,
        # within the validated input boundary, without rendering dependency.
        result["activate"] = lambda: widget.emit("clicked")
    elif isinstance(widget, (Gtk.CheckButton, Gtk.Entry, Gtk.SearchEntry)):
        result["activate"] = lambda: widget.emit("activate")
    if _is_surface(widget):
        result["close"] = lambda: _close_surface(widget)
    result.update(_binding(widget).callbacks)
    return result


class GtkUIAdapter:
    """Thin toolkit adapter; all desktop-neutral transport lives in ApplicationUI."""

    def __init__(self, application):
        self.application = application

    def _owns(self, window):
        seen = set()
        while window is not None and window not in seen:
            seen.add(window)
            if window.get_application() == self.application:
                return True
            window = window.get_transient_for()
        return False

    def _surfaces(self):
        Gtk = _gtk()
        model = Gtk.Window.get_toplevels()
        surfaces = []
        if model.get_n_items() > 1024:
            raise UIError("Unavailable")
        for index in range(model.get_n_items()):
            root = model.get_item(index)
            if not self._owns(root):
                continue
            if _identity(root):
                surfaces.append(root)
            if hasattr(root, "get_dialogs"):
                dialogs = root.get_dialogs()
                for dialog_index in range(dialogs.get_n_items()):
                    dialog = dialogs.get_item(dialog_index)
                    if _identity(dialog):
                        surfaces.append(dialog)
            elif not _identity(root):
                # An Adw.Dialog may use an anonymous native host. Its owner is
                # still validated through the public transient-window chain.
                surfaces.extend(widget for widget in _walk(root)
                                if _identity(widget) and _is_surface(widget))
        surfaces = list(dict.fromkeys(surfaces))
        identities = [_identity(surface) for surface in surfaces]
        if len(identities) != len(set(identities)):
            raise UIError("Unavailable")
        return surfaces

    def _surface(self, surface_id):
        if type(surface_id) is not str or len(surface_id) > 255 or not _ID.fullmatch(surface_id):
            raise UIError("InvalidArgument")
        surfaces = self._surfaces()
        matches = [surface for surface in surfaces if _identity(surface) == surface_id]
        if len(matches) != 1:
            raise UIError("Unavailable")
        return matches[0], surfaces

    @staticmethod
    def _parent_surface(surface):
        Gtk = _gtk()
        parent = (surface.get_transient_for() if isinstance(surface, Gtk.Window)
                  else surface.get_parent())
        while parent is not None:
            if _identity(parent) and _is_surface(parent):
                return _identity(parent)
            parent = (parent.get_transient_for() if isinstance(parent, Gtk.Window)
                      else parent.get_parent())
        return None

    @staticmethod
    def _modal(surface):
        return bool(surface.get_modal()) if hasattr(surface, "get_modal") else True

    def _blocked(self, surface, surfaces):
        owner_ids = {_identity(surface)}
        parent = self._parent_surface(surface)
        while parent is not None and parent not in owner_ids:
            owner_ids.add(parent)
            ancestor = next((item for item in surfaces if _identity(item) == parent), None)
            parent = self._parent_surface(ancestor) if ancestor is not None else None
        return any(_visible(item) and self._modal(item)
                   and _identity(item) not in owner_ids for item in surfaces)

    def list_surfaces(self):
        return [{"id": _identity(surface),
                 "application_id": self.application.get_application_id(),
                 "type": surface.__gtype__.name, "visible": _visible(surface),
                 "enabled": bool(surface.is_sensitive()),
                 "modal": self._modal(surface),
                 "parent_id": self._parent_surface(surface)}
                for surface in self._surfaces()]

    def _elements(self, surface):
        elements = {}
        pending = [surface]
        count = 0
        while pending:
            widget = pending.pop()
            count += 1
            if count > _MAX_WIDGETS:
                raise UIError("Unavailable")
            # A nested dialog has its own scope, independent of native hosting.
            if widget is not surface and _is_surface(widget) and _identity(widget):
                continue
            identity = _identity(widget)
            for element_id in set((identity,) + _binding(widget).aliases) - {""}:
                if element_id in elements:
                    raise UIError("Unavailable")
                elements[element_id] = widget
                if len(elements) > _MAX_WIDGETS:
                    raise UIError("Unavailable")
            pending.extend(_children(widget))
        return elements

    def _metadata(self, surface, element_id, widget, *, snapshot=False):
        binding = _binding(widget)
        virtual = binding.dispatcher is not None and element_id in binding.aliases
        callbacks = _generic(widget)
        operations = (binding.operations if virtual else callbacks.keys())
        parent = widget.get_parent()
        while parent is not None and parent is not surface and not _identity(parent):
            parent = parent.get_parent()
        parent_id = (_identity(widget) if virtual and _identity(widget) != element_id
                     else _identity(parent) if parent is not None else None)
        if widget is surface:
            parent_id = None
        result = {"id": element_id, "surface_id": _identity(surface),
                  "application_id": self.application.get_application_id(),
                  "type": "document-element" if virtual else widget.__gtype__.name,
                  "visible": _visible(widget), "enabled": bool(widget.is_sensitive()),
                  "operations": sorted(set(operations) | {"getElementById"}),
                  "parent_id": parent_id,
                  "role": widget.get_accessible_role().value_nick}
        if snapshot and not virtual:
            from .translation_widgets import accessible_metadata
            result.update(accessible_metadata(widget))
            if hasattr(widget, "get_title") and hasattr(widget, "get_subtitle"):
                result["name"] = result["name"] or widget.get_title() or ""
                result["description"] = result["description"] or widget.get_subtitle() or ""
            for operation, field_name in (("getValue", "value"), ("getText", "text"),
                                          ("getChoices", "choices")):
                if operation in callbacks:
                    result[field_name] = callbacks[operation]()
        return result

    @staticmethod
    def _arguments(operation, arguments):
        if operation == "inventory":
            if not set(arguments) <= {"offset", "limit", "revision"}:
                raise UIError("InvalidArgument")
            offset, limit = arguments.get("offset", 0), arguments.get("limit", 128)
            revision = arguments.get("revision")
            if (type(offset) is not int or offset < 0 or offset > _MAX_WIDGETS
                    or type(limit) is not int or not 1 <= limit <= 256
                    or (revision is not None and (type(revision) is not str
                        or not re.fullmatch(r"[a-f0-9]{64}", revision)))
                    or (offset and revision is None)):
                raise UIError("InvalidArgument")
            return
        expected = ({"value"} if operation == "setValue" else
                    {"text"} if operation == "setText" else set())
        if set(arguments) != expected:
            raise UIError("InvalidArgument")
        if operation == "setText":
            _strict_text(arguments["text"])

    def call(self, surface_id, element_id, operation, arguments, complete):
        """Execute once; asynchronous aliases complete within a bounded lifetime."""
        if threading.current_thread() is not threading.main_thread():
            raise UIError("Failed")
        if type(operation) is not str or len(operation) > 32 or operation not in _OPERATIONS | {"inventory"}:
            raise UIError("Unsupported")
        _validate_json(arguments)
        if type(arguments) is not dict:
            raise UIError("InvalidArgument")
        self._arguments(operation, arguments)
        surface, surfaces = self._surface(surface_id)
        elements = self._elements(surface)
        if operation == "inventory":
            if element_id != "":
                raise UIError("InvalidArgument")
            inventory = [self._metadata(surface, identity, widget)
                         for identity, widget in sorted(elements.items())]
            digest = hashlib.sha256()
            for item in inventory:
                digest.update(_encode(item).encode("utf-8"))
                digest.update(b"\n")
            revision = digest.hexdigest()
            if arguments.get("revision", revision) != revision:
                raise UIError("Unavailable")
            offset, limit = arguments.get("offset", 0), arguments.get("limit", 128)
            if offset > len(inventory):
                raise UIError("InvalidArgument")
            next_offset = offset + limit if offset + limit < len(inventory) else None
            complete({"elements": inventory[offset:offset + limit],
                      "next_offset": next_offset, "revision": revision})
            return
        if type(element_id) is not str or len(element_id) > 255 or not _ID.fullmatch(element_id):
            raise UIError("InvalidArgument")
        widget = elements.get(element_id)
        if widget is None or widget.get_root() != surface.get_root():
            raise UIError("Unavailable")
        if operation in _INPUTS:
            if (not _visible(widget) or not widget.is_sensitive()
                    or not _visible(surface) or self._blocked(surface, surfaces)):
                raise UIError("Unavailable")
        binding = _binding(widget)
        if binding.dispatcher is not None and element_id in binding.aliases:
            if operation not in binding.operations:
                raise UIError("Unsupported")
            host_reference = widget.weak_ref()

            def dispatched(result, error=None):
                if threading.current_thread() is not threading.main_thread():
                    from gi.repository import GLib
                    def on_main():
                        dispatched(result, error)
                        return GLib.SOURCE_REMOVE
                    GLib.idle_add(on_main)
                    return
                if error is not None:
                    complete(None, error)
                    return
                try:
                    current_surface, _ = self._surface(surface_id)
                    current_host = self._elements(current_surface).get(element_id)
                    if (current_host is None or current_host != host_reference()
                            or _binding(current_host) is not binding
                            or current_host.get_root() != current_surface.get_root()):
                        raise UIError("Failed")
                except Exception:
                    complete(None, UIError("Failed"))
                    return
                if operation == "getElementById":
                    if type(result) is not dict:
                        complete(None, UIError("Failed"))
                        return
                    merged = dict(result)
                    fresh_metadata = self._metadata(current_surface, element_id, current_host)
                    # Document roles describe the actual identified editor
                    # control, rather than its containing WebKit widget.
                    if type(result.get("role")) is str:
                        fresh_metadata["role"] = result["role"]
                    merged.update(fresh_metadata)
                    precise_operations = result.get("operations", [])
                    if (type(precise_operations) is not list
                            or any(type(item) is not str for item in precise_operations)):
                        complete(None, UIError("Failed"))
                        return
                    merged["operations"] = sorted(set(precise_operations)
                        & set(fresh_metadata["operations"]) | {"getElementById"})
                    merged["visible"] = bool(result.get("visible", False)) and fresh_metadata["visible"]
                    merged["enabled"] = bool(result.get("enabled", False)) and fresh_metadata["enabled"]
                    complete(merged)
                else:
                    complete(None if operation in _INPUTS else result)

            binding.dispatcher(operation, {**arguments, "element_id": element_id}, dispatched)
            return
        if operation == "getElementById":
            complete(self._metadata(surface, element_id, widget, snapshot=True))
            return
        callbacks = _generic(widget)
        if operation not in callbacks:
            raise UIError("Unsupported")
        result = (callbacks[operation](arguments["value"]) if operation == "setValue"
                  else callbacks[operation](arguments["text"]) if operation == "setText"
                  else callbacks[operation]())
        complete(None if operation in _INPUTS else result)


class ApplicationUI:
    """Lifecycle-bound, same-user UI transport, independent of desktop/toolkit.

    An adapter supplies ``list_surfaces()`` and
    ``call(surface_id, element_id, operation, arguments, complete)``. GTK is the
    default adapter; neither protocol nor client requires a desktop environment.
    """

    def __init__(self, application, *, adapter=None):
        self.adapter = adapter if adapter is not None else GtkUIAdapter(application)
        self._connection = None
        self._registration = 0
        self._pending = {}
        self._serial = 0
        self._active_input = None

    def register(self, connection, object_path):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Application UI must register on the main thread")
        if self._registration:
            raise RuntimeError("Application UI is already registered")
        from gi.repository import Gio
        info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
        self._registration = connection.register_object(
            object_path, info.interfaces[0], self._method_call, None, None)
        if not self._registration:
            raise RuntimeError("Application UI registration failed")
        self._connection = connection

    def unregister(self, connection):
        if self._connection is not None and connection is not self._connection:
            raise RuntimeError("Application UI connection changed")
        from gi.repository import GLib
        for request in list(self._pending.values()):
            GLib.source_remove(request.source)
            request.cancellable.cancel()
            self._error(request.invocation, "Unavailable")
        self._pending.clear()
        self._active_input = None
        if self._registration:
            connection.unregister_object(self._registration)
        self._registration = 0
        self._connection = None

    def list_surfaces(self):
        return self.adapter.list_surfaces()

    def call(self, surface_id, element_id, operation, arguments, complete):
        return self.adapter.call(surface_id, element_id, operation, arguments, complete)

    @staticmethod
    def _error(invocation, code):
        codes = {"InvalidArgument", "Unavailable", "Unsupported", "Denied", "Failed", "Timeout"}
        if code not in codes:
            code = "Failed"
        invocation.return_dbus_error(INTERFACE + "." + code,
                                     "Application UI operation " + code.lower())

    def _authorize(self, connection, sender, cancellable, complete):
        from gi.repository import Gio, GLib
        if connection is not self._connection or not sender or not sender.startswith(":"):
            complete(UIError("Denied"))
            return

        def credentials_ready(bus, result, *_user_data):
            try:
                credentials = bus.call_finish(result)
                if credentials.unpack()[0] != os.getuid():
                    raise UIError("Denied")
            except Exception:
                complete(UIError("Denied"))
                return
            complete(None)

        connection.call(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "GetConnectionUnixUser", GLib.Variant("(s)", (sender,)),
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 2000,
            cancellable, credentials_ready)

    def _method_call(self, connection, sender, _path, _interface, method,
                     parameters, invocation):
        from gi.repository import Gio, GLib
        try:
            if method not in {"Call", "ListSurfaces"}:
                raise UIError("Unsupported")
            if len(self._pending) >= _MAX_PENDING:
                raise UIError("Unavailable")
            mutation = False
            if method == "Call":
                surface_id, element_id, operation, encoded = parameters.unpack()
                arguments = _decode(encoded)
                mutation = operation in _INPUTS
                if mutation and self._active_input is not None:
                    raise UIError("Unavailable")
            self._serial += 1
            serial = self._serial
            if mutation:
                self._active_input = serial
            cancellable = Gio.Cancellable()

            def expired():
                request = self._pending.pop(serial, None)
                if request is not None:
                    request.cancellable.cancel()
                    # A timed-out provider may still be applying input. Keep
                    # subsequent input blocked until its completion or teardown.
                    if self._active_input == serial and not request.input_dispatched:
                        self._active_input = None
                    self._error(invocation, "Timeout")
                return GLib.SOURCE_REMOVE

            source = GLib.timeout_add_seconds(_TIMEOUT_SECONDS, expired)
            self._pending[serial] = _Request(source, invocation, cancellable)

            def complete(result, error=None):
                if self._active_input == serial:
                    self._active_input = None
                request = self._pending.pop(serial, None)
                if request is None:
                    return
                GLib.source_remove(request.source)
                if error is not None:
                    self._error(invocation, error.code if isinstance(error, UIError)
                                else "InvalidArgument" if isinstance(error, ValueError)
                                else "Failed")
                    return
                try:
                    encoded_result = _encode(result)
                except (ValueError, TypeError, UnicodeError):
                    self._error(invocation, "Failed")
                    return
                invocation.return_value(GLib.Variant("(s)", (encoded_result,)))

            def authorized(error):
                request = self._pending.get(serial)
                if request is None:
                    return
                if error is not None:
                    complete(None, error)
                    return
                try:
                    if method == "ListSurfaces":
                        complete(self.list_surfaces())
                    else:
                        request.input_dispatched = mutation
                        self.call(surface_id, element_id, operation, arguments, complete)
                except Exception as failure:
                    complete(None, failure)

            try:
                self._authorize(connection, sender, cancellable, authorized)
            except Exception as error:
                complete(None, error)
        except UIError as error:
            self._error(invocation, error.code)
        except (ValueError, TypeError, UnicodeError):
            self._error(invocation, "InvalidArgument")
        except Exception:
            self._error(invocation, "Failed")
