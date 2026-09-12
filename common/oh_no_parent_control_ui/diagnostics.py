"""Request the bounded product-log archive through the authorized broker."""

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from .diagnostic_bundle import with_system_info
from .system_info import collect_system_info

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

LOG = get_logger("diagnostics")
BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
MAX_BYTES = 16 * 1024 * 1024


def collect_logs():
    """Return all components' logs without granting filesystem access to the UI."""
    LOG.info("diagnostics.001")
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
    LOG.info("diagnostics.002", bytes=len(data))
    return with_system_info(bytes(data), collect_system_info(connection))
