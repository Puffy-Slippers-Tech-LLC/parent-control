"""System-bus service entry point."""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from . import config
from .adapters import AccountsService, CallerCredentials, PolkitAuthorizer
from .core import Broker, BrokerError

BUS_NAME = "com.puffyslippers.OhNoParentControl1"
OBJECT_PATH = "/com/puffyslippers/OhNoParentControl1"
INTERFACE = BUS_NAME
CONFIG_PATH = os.environ.get("OH_NO_PARENT_CONTROL_CONFIG", "/etc/oh-no-parent-control/config.json")

INTROSPECTION_XML = f"""
<node>
  <interface name="{INTERFACE}">
    <method name="GetRequestOptions">
      <arg name="child_label" type="s" direction="out"/>
      <arg name="durations" type="a(ss)" direction="out"/>
      <arg name="filter_profiles" type="a(ss)" direction="out"/>
    </method>
    <method name="RequestAccess">
      <arg name="duration_id" type="s" direction="in"/>
      <arg name="filter_profile_id" type="s" direction="in"/>
      <arg name="correlation_id" type="s" direction="out"/>
      <arg name="result_code" type="s" direction="out"/>
    </method>
  </interface>
</node>
"""


class Service:
    def __init__(self, connection):
        self.connection = connection
        self.credentials = CallerCredentials(connection)
        self.broker = Broker(
            lambda: config.load(CONFIG_PATH), PolkitAuthorizer(connection),
            AccountsService(connection), caller_alive=self.credentials.alive,
        )
        self.node_info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)

    def register(self):
        self.connection.register_object(
            OBJECT_PATH, self.node_info.interfaces[0], self._method_call, None, None
        )

    def _method_call(self, _connection, sender, _path, _interface, method,
                     parameters, invocation):
        try:
            caller_uid = self.credentials.uid(sender)
            if method == "GetRequestOptions":
                options = self.broker.get_options(caller_uid)
                invocation.return_value(GLib.Variant(
                    "(sa(ss)a(ss))",
                    (options.child_label, options.durations, options.filter_profiles),
                ))
            elif method == "RequestAccess":
                duration_id, profile_id = parameters.unpack()
                threading.Thread(
                    target=self._request_worker,
                    args=(invocation, caller_uid, sender, duration_id, profile_id),
                    daemon=True,
                ).start()
            else:
                invocation.return_dbus_error(
                    f"{BUS_NAME}.Error.InvalidRequest", "unknown method"
                )
        except BrokerError as error:
            invocation.return_dbus_error(error.dbus_name, str(error))
        except Exception:
            logging.exception("[oh-no-parent-control] request dispatch failed")
            invocation.return_dbus_error(f"{BUS_NAME}.Error.Failed", "service failure")

    def _request_worker(self, invocation, caller_uid, sender, duration_id, profile_id):
        try:
            result = self.broker.request_access(
                caller_uid, sender, duration_id, profile_id
            )
            GLib.idle_add(self._return_value, invocation, result)
        except BrokerError as error:
            GLib.idle_add(self._return_error, invocation, error.dbus_name, str(error))
        except Exception:
            logging.exception("[oh-no-parent-control] request failed")
            GLib.idle_add(
                self._return_error, invocation, f"{BUS_NAME}.Error.Failed", "service failure"
            )

    @staticmethod
    def _return_value(invocation, result):
        invocation.return_value(GLib.Variant("(ss)", result))
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _return_error(invocation, name, message):
        invocation.return_dbus_error(name, message)
        return GLib.SOURCE_REMOVE


def main():
    logging.basicConfig(level=logging.INFO, format="[oh-no-parent-control] %(levelname)s %(message)s")
    if os.geteuid() != 0:
        logging.critical("broker must run as root")
        return 1
    loop = GLib.MainLoop()
    service_holder = []

    def on_bus_acquired(_connection, _name):
        service = Service(_connection)
        service.register()
        service_holder.append(service)

    def on_name_lost(_connection, _name):
        logging.critical("could not own the system-bus name")
        loop.quit()

    owner_id = Gio.bus_own_name(
        Gio.BusType.SYSTEM, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
        on_bus_acquired, None, on_name_lost,
    )
    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, loop.quit)
    try:
        loop.run()
    finally:
        Gio.bus_unown_name(owner_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
