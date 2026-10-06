"""Public, owner-pinned Python facade for the Application UI session-bus API.

Construct a new client deliberately when an application restarts. Calls are
single-use and never replayed. Read the relevant public result independently
after a mutation; a successful call acknowledges UI input, not a policy save.
"""

from __future__ import annotations

import os
import re

from .application_ui import INTERFACE, _decode, _encode, _ID


# Stable logical endpoints, independent of distribution, compositor or toolkit.
# A future desktop adapter implements these same buses, paths, scopes and IDs.
_ENDPOINTS = {
    "kiosk-notifications": ("com.puffyslippers.OhNoParentControl.KioskNotifications",
                            "/com/puffyslippers/OhNoParentControl/KioskNotifications", "kiosk-system-notification"),
    "parent": ("com.puffyslippers.OhNoParentControl.Parent",
               "/com/puffyslippers/OhNoParentControl/Parent", "parent-window"),
    "kiosk": ("com.puffyslippers.OhNoParentControl",
              "/com/puffyslippers/OhNoParentControl", "kiosk-request-window"),
    "child-request": ("com.puffyslippers.OhNoParentControl.ChildRequest",
                      "/com/puffyslippers/OhNoParentControl/ChildRequest", "kiosk-request-window"),
    "child-panel": ("com.puffyslippers.OhNoParentControl.ChildUI",
                    "/com/puffyslippers/OhNoParentControl/ApplicationUI", "child-screen-time-indicator"),
}


class UIClientError(RuntimeError):
    def __init__(self, code, *, uncertain=False):
        self.code = code
        self.uncertain = uncertain
        super().__init__("Application UI operation " + code)


class UIClient:
    """Connect to one same-user application process and retain its bus owner.

    ``surface_id`` supplies the optional default scope. ``object_path`` defaults
    to the GApplication path derived from ``application_id``. The Child Shell
    extension uses its documented explicit object path instead.
    """

    def __init__(self, application_id, *, surface_id=None, object_path=None, owner=None,
                 connection=None, timeout_msec=15000):
        from gi.repository import Gio
        if owner is not None and (type(owner) is not str or not Gio.dbus_is_name(owner)
                                  or not owner.startswith(":") or object_path is None):
            raise ValueError("A unique owner requires its explicit object path")
        if type(application_id) is str and application_id in _ENDPOINTS:
            application_id, default_path, default_surface = _ENDPOINTS[application_id]
            object_path = object_path or default_path
            surface_id = surface_id or default_surface
        if (type(application_id) is not str or not Gio.dbus_is_name(application_id)
                or application_id.startswith(":")):
            raise ValueError("Invalid application bus name")
        if (type(timeout_msec) is not int or timeout_msec < 1
                or timeout_msec > 60000):
            raise ValueError("Invalid UI timeout")
        if surface_id is not None and (type(surface_id) is not str
                                       or not _ID.fullmatch(surface_id)):
            raise ValueError("Invalid surface identity")
        object_path = object_path or "/" + application_id.replace(".", "/")
        if (type(object_path) is not str
                or not re.fullmatch(r"/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?", object_path)):
            raise ValueError("Invalid application object path")
        self.application_id = application_id
        self.surface_id = surface_id
        self.object_path = object_path
        self.timeout_msec = timeout_msec
        self.connection = connection or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._owner_supplied = owner is not None
        self.owner = owner or self._bus("GetNameOwner", "(s)", (application_id,), "(s)")[0]
        if not self.owner.startswith(":"):
            raise UIClientError("Denied")
        uid = self._bus("GetConnectionUnixUser", "(s)", (self.owner,), "(u)")[0]
        if uid != os.getuid():
            raise UIClientError("Denied")
        self.pid = self._bus("GetConnectionUnixProcessID", "(s)", (self.owner,), "(u)")[0]
        self._check_owner()

    def _bus(self, method, signature, arguments, result_signature):
        from gi.repository import Gio, GLib
        try:
            result = self.connection.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                method, GLib.Variant(signature, arguments),
                GLib.VariantType.new(result_signature), Gio.DBusCallFlags.NONE,
                self.timeout_msec, None)
            return result.unpack()
        except GLib.Error as error:
            raise UIClientError("Unavailable") from error

    def _check_owner(self, *, uncertain=False):
        try:
            name = self.owner if self._owner_supplied else self.application_id
            owner = self._bus("GetNameOwner", "(s)", (name,), "(s)")[0]
            if self._owner_supplied:
                uid = self._bus("GetConnectionUnixUser", "(s)", (self.owner,), "(u)")[0]
                pid = self._bus("GetConnectionUnixProcessID", "(s)", (self.owner,), "(u)")[0]
                if uid != os.getuid() or pid != self.pid:
                    raise UIClientError("OwnerChanged")
        except UIClientError as error:
            raise UIClientError("OwnerChanged", uncertain=uncertain) from error
        if owner != self.owner:
            raise UIClientError("OwnerChanged", uncertain=uncertain)

    def _request(self, method, parameters, *, mutation=False):
        from gi.repository import Gio, GLib
        self._check_owner()
        try:
            result = self.connection.call_sync(
                self.owner, self.object_path, INTERFACE, method, parameters,
                GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NONE,
                self.timeout_msec, None)
        except GLib.Error as error:
            remote = Gio.DBusError.get_remote_error(error) or ""
            code = remote.removeprefix(INTERFACE + ".")
            known = {"InvalidArgument", "Unavailable", "Unsupported", "Denied", "Failed", "Timeout"}
            # An asynchronous provider can fail after accepting input. A
            # timeout/transport/provider failure never authorizes replay.
            raise UIClientError(code if code in known else "Transport",
                                uncertain=mutation) from error
        # The call targets the pinned unique owner, so its successful reply
        # acknowledges that process's input even when the handler quits the
        # application. Reads still require a live owner after the exchange;
        # every subsequent call rechecks ownership before dispatching input.
        if not mutation:
            self._check_owner()
        try:
            encoded, = result.unpack()
            decoded = _decode(encoded, require_dict=False)
            if mutation and decoded is not None:
                raise ValueError("Invalid mutation acknowledgement")
            return decoded
        except (ValueError, TypeError, KeyError) as error:
            raise UIClientError("InvalidResponse", uncertain=mutation) from error

    def listSurfaces(self):
        result = self._request("ListSurfaces", None)
        if type(result) is not list or any(type(surface) is not dict for surface in result):
            raise UIClientError("InvalidResponse")
        ids = [surface.get("id") for surface in result]
        if (any(type(identity) is not str or not _ID.fullmatch(identity) for identity in ids)
                or len(ids) != len(set(ids))
                or any(surface.get("application_id") != self.application_id for surface in result)):
            raise UIClientError("InvalidResponse")
        return result

    def call(self, surface_id, element_id, operation, arguments=None):
        from gi.repository import GLib
        if arguments is None:
            arguments = {}
        if type(arguments) is not dict:
            raise ValueError("UI arguments must be an object")
        encoded = _encode(arguments)
        return self._request("Call", GLib.Variant("(ssss)", (
            surface_id, element_id, operation, encoded)),
            mutation=operation in {"setValue", "setText", "activate", "close"})

    def getSurfaceById(self, surface_id):
        if not any(surface["id"] == surface_id for surface in self.listSurfaces()):
            raise UIClientError("Unavailable")
        return UISurface(self, surface_id)

    def getElementById(self, element_id, *, surface_id=None):
        if type(element_id) is not str or not _ID.fullmatch(element_id):
            raise ValueError("Invalid element identity")
        scope = self._resolve_scope(element_id, surface_id)
        element = UIElement(self, scope, element_id)
        element.snapshot()
        return element

    def _resolve_scope(self, element_id, surface_id=None):
        if type(element_id) is not str or not _ID.fullmatch(element_id):
            raise ValueError("Invalid element identity")
        scope = surface_id or self.surface_id
        if scope is None:
            matches = []
            for surface in self.listSurfaces():
                inventory = self.inventory(surface["id"])
                if any(item.get("id") == element_id for item in inventory):
                    matches.append(surface["id"])
            if len(matches) != 1:
                raise UIClientError("Unavailable")
            scope = matches[0]
        return scope

    def inventory(self, surface_id=None):
        scope = surface_id or self.surface_id
        if scope is None:
            raise ValueError("Inventory requires a surface identity")
        inventory, ids, offset, revision = [], set(), 0, None
        while True:
            arguments = {"offset": offset, "limit": 128}
            if revision is not None:
                arguments["revision"] = revision
            page = self.call(scope, "", "inventory", arguments)
            if type(page) is not dict or set(page) != {"elements", "next_offset", "revision"}:
                raise UIClientError("InvalidResponse")
            elements, next_offset, page_revision = page["elements"], page["next_offset"], page["revision"]
            if (type(elements) is not list or len(elements) > 128
                    or type(page_revision) is not str
                    or not re.fullmatch(r"[a-f0-9]{64}", page_revision)
                    or (revision is not None and revision != page_revision)):
                raise UIClientError("InvalidResponse")
            for element in elements:
                if (type(element) is not dict or type(element.get("id")) is not str
                        or not _ID.fullmatch(element["id"]) or element["id"] in ids
                        or element.get("surface_id") != scope
                        or element.get("application_id") != self.application_id):
                    raise UIClientError("InvalidResponse")
                ids.add(element["id"])
                inventory.append(element)
            if len(inventory) > 100000:
                raise UIClientError("InvalidResponse")
            if next_offset is None:
                return inventory
            if (type(next_offset) is not int or not elements
                    or next_offset != offset + len(elements)):
                raise UIClientError("InvalidResponse")
            offset, revision = next_offset, page_revision

    def _element_call(self, element_id, operation, arguments=None, *, surface_id=None):
        scope = self._resolve_scope(element_id, surface_id)
        return self.call(scope, element_id, operation, arguments)

    def getValue(self, element_id, *, surface_id=None):
        return self._element_call(element_id, "getValue", surface_id=surface_id)

    def setValue(self, element_id, value, *, surface_id=None):
        return self._element_call(element_id, "setValue", {"value": value}, surface_id=surface_id)

    def getText(self, element_id, *, surface_id=None):
        return self._element_call(element_id, "getText", surface_id=surface_id)

    def setText(self, element_id, text, *, surface_id=None):
        return self._element_call(element_id, "setText", {"text": text}, surface_id=surface_id)

    def getChoices(self, element_id, *, surface_id=None):
        return self._element_call(element_id, "getChoices", surface_id=surface_id)

    def activate(self, element_id, *, surface_id=None):
        return self._element_call(element_id, "activate", surface_id=surface_id)

    def close(self, element_id=None, *, surface_id=None):
        scope = surface_id or self.surface_id
        target = element_id or scope
        if target is None:
            raise ValueError("Close requires a surface identity")
        return self._element_call(target, "close", surface_id=scope)


class UISurface:
    def __init__(self, client, surface_id):
        self.client = client
        self.id = surface_id

    def getElementById(self, element_id):
        return self.client.getElementById(element_id, surface_id=self.id)

    def inventory(self):
        return self.client.inventory(self.id)

    def getValue(self, element_id):
        return self.client.getValue(element_id, surface_id=self.id)

    def setValue(self, element_id, value):
        return self.client.setValue(element_id, value, surface_id=self.id)

    def getText(self, element_id):
        return self.client.getText(element_id, surface_id=self.id)

    def setText(self, element_id, text):
        return self.client.setText(element_id, text, surface_id=self.id)

    def getChoices(self, element_id):
        return self.client.getChoices(element_id, surface_id=self.id)

    def activate(self, element_id):
        return self.client.activate(element_id, surface_id=self.id)

    def close(self):
        return self.client.close(self.id, surface_id=self.id)


class UIElement:
    """An identity reference: every read and input resolves the live widget anew."""

    def __init__(self, client, surface_id, element_id):
        self.client = client
        self.surface_id = surface_id
        self.id = element_id

    def _call(self, operation, arguments=None):
        return self.client.call(self.surface_id, self.id, operation, arguments)

    def snapshot(self):
        result = self._call("getElementById")
        if (type(result) is not dict or result.get("id") != self.id
                or result.get("surface_id") != self.surface_id
                or result.get("application_id") != self.client.application_id):
            raise UIClientError("InvalidResponse")
        return result

    @property
    def value(self):
        return self._call("getValue")

    @value.setter
    def value(self, value):
        self._call("setValue", {"value": value})

    @property
    def text(self):
        return self._call("getText")

    @text.setter
    def text(self, text):
        self._call("setText", {"text": text})

    @property
    def choices(self):
        return self._call("getChoices")

    @property
    def visible(self):
        return self.snapshot()["visible"]

    @property
    def enabled(self):
        return self.snapshot()["enabled"]

    def activate(self):
        self._call("activate")

    def close(self):
        self._call("close")

    def getValue(self):
        return self.value

    def setValue(self, value):
        self.value = value

    def getText(self):
        return self.text

    def setText(self, text):
        self.text = text

    def getChoices(self):
        return self.choices
