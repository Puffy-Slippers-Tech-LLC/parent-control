"""Request the bounded product-log archive through the authorized broker."""

import logging

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

LOG = logging.getLogger("oh-no-parent-control-ui")
BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
MAX_BYTES = 16 * 1024 * 1024


def collect_logs():
    """Return all components' logs without granting filesystem access to the UI."""
    LOG.info("diagnostic archive requested source=broker")
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        reply = connection.call_sync(
            BUS_NAME, OBJECT_PATH, BUS_NAME, "ExportDiagnosticLogs", None,
            GLib.VariantType.new("(ay)"), Gio.DBusCallFlags.NONE, 30_000, None,
        )
    except GLib.Error as error:
        # Preserve the existing collection failure contract for send/download.
        # D-Bus exception messages can contain private details; never log them.
        raise OSError("Diagnostic export unavailable") from error
    data = reply.get_child_value(0).get_data_as_bytes().get_data()
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Invalid diagnostic archive size")
    LOG.info("diagnostic archive ready bytes=%d", len(data))
    return bytes(data)
