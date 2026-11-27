"""Saved-time broker transport for the request form and Parent."""

from typing import NamedTuple

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
GRANT_STATUS_SIGNATURE = "(ttuuuuuustuu)"
STATUS_TIMEOUT_MS = 30_000
TRANSFER_TIMEOUT_MS = 120_000
# G_MAXINT disables Gio's timeout while the approver decides.
REQUEST_TIMEOUT_MS = GLib.MAXINT


class GrantStatus(NamedTuple):
    revision: int
    evaluated_at_epoch_seconds: int
    daily_remaining_seconds: int
    running_remaining_seconds: int
    running_beyond_daily_seconds: int
    saved_seconds: int
    usable_seconds: int
    total_seconds: int
    running_mode: str
    running_end_epoch_seconds: int
    immediate_estimate_seconds: int
    deferred_estimate_seconds: int


class DeferredApproval(NamedTuple):
    correlation_id: str
    result_code: str
    pause_error: str


def saved_time_method_missing(error):
    """Recognize the compatibility reply by its exact D-Bus error name."""
    return (isinstance(error, GLib.Error) and Gio.DBusError.get_remote_error(error) ==
            "org.freedesktop.DBus.Error.UnknownMethod")


def call_broker_async(connection, method, parameters, signature, done, timeout):
    if connection is None:
        raise RuntimeError("the preview does not have a broker connection")
    connection.call(
        BUS_NAME, OBJECT_PATH, INTERFACE, method, parameters,
        GLib.VariantType.new(signature), Gio.DBusCallFlags.NONE, timeout, None, done,
    )


class RequestGrantClient:
    """Complete with (reply, error), using (None, None) for an older broker.

    A completed transfer has an empty tuple reply. Other call errors keep
    their D-Bus identity so the form can refresh status without resubmitting.
    """

    def __init__(self, connection):
        self._connection = connection

    def get_grant_status(self, target_uid, requested_seconds, done):
        self._call(
            "GetGrantStatus", GLib.Variant("(uu)", (target_uid, requested_seconds)),
            GRANT_STATUS_SIGNATURE, STATUS_TIMEOUT_MS, done, GrantStatus,
        )

    def request_deferred_access(self, target_uid, approver_uid, duration_seconds,
                                allow_soft_blocked_apps, revision, done):
        self._call(
            "RequestDeferredAccess",
            GLib.Variant("(uuubt)", (target_uid, approver_uid, duration_seconds,
                                    allow_soft_blocked_apps, revision)),
            "(sss)", REQUEST_TIMEOUT_MS, done, DeferredApproval,
        )

    def pause_grant(self, target_uid, revision, done):
        self._transfer("PauseGrant", target_uid, revision, done)

    def use_saved_time(self, target_uid, revision, done):
        self._transfer("UseSavedTime", target_uid, revision, done)

    def _transfer(self, method, target_uid, revision, done):
        self._call(method, GLib.Variant("(ut)", (target_uid, revision)),
                   "()", TRANSFER_TIMEOUT_MS, done)

    def _call(self, method, parameters, signature, timeout, done, reply_type=None):
        def completed(connection, result):
            try:
                values = connection.call_finish(result).unpack()
                reply = values if reply_type is None else reply_type(*values)
            except Exception as error:
                done(None, None if saved_time_method_missing(error) else error)
            else:
                done(reply, None)

        call_broker_async(self._connection, method, parameters, signature, completed, timeout)
