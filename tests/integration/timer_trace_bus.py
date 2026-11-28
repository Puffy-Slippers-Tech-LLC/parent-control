"""Shared guest-side Malcontent D-Bus monitor."""

import time


def monitor_timer(emit, *, extra_rules=()):
    from gi.repository import Gio, GLib

    bus = Gio.DBusConnection.new_for_address_sync(Gio.dbus_address_get_for_bus_sync(
        Gio.BusType.SYSTEM, None), Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)

    def receive(connection, message, incoming, _data):
        if incoming:
            monotonic, wall = time.monotonic(), time.time()
            body = message.get_body()
            emit('message', kind=int(message.get_message_type()), sender=message.get_sender(),
                 destination=message.get_destination(), serial=message.get_serial(),
                 reply_serial=message.get_reply_serial(), interface=message.get_interface(),
                 member=message.get_member(), path=message.get_path(),
                 error_name=message.get_error_name(), monotonic=monotonic, wall=wall,
                 body=body.print_(True) if body is not None else '')
        # GDBus must never answer another client's monitored call.
        return message if not incoming or message.get_destination() == connection.get_unique_name() else None

    bus.add_filter(receive, None)
    rules = ["interface='org.freedesktop.MalcontentTimer1.Child'",
             "interface='org.freedesktop.MalcontentTimer1.Parent'",
             "sender='org.freedesktop.MalcontentTimer1'", *extra_rules]
    bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                  'org.freedesktop.DBus.Monitoring', 'BecomeMonitor',
                  GLib.Variant('(asu)', (rules, 0)), None, Gio.DBusCallFlags.NONE, 5000, None)
    return bus
