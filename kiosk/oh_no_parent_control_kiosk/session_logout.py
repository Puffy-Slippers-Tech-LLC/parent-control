"""Cooperate with GNOME's public logout protocol before exiting the station."""

from gi.repository import Gio, GLib

NAME = 'org.gnome.SessionManager'
PATH = '/org/gnome/SessionManager'
CLIENT = NAME + '.ClientPrivate'


class KioskLogout:
    def __init__(self, application):
        self._application = application
        self._connection = None
        self._subscription = self._deadline = 0
        self._started = self._closed = False
        self._client = None

    def begin(self):
        if self._started or self._closed:
            return
        self._started = True
        # OnSuccess on the app unit remains the fallback. Bound the extra
        # handoff time if the manager is missing, unresponsive or shutting down.
        self._deadline = GLib.timeout_add(750, self._expired)
        try:
            self._connection = self._application.get_dbus_connection()
            if self._connection is None:
                self._finish()
                return
            self._call(PATH, NAME, 'RegisterClient', GLib.Variant('(ss)', (
                self._application.get_application_id(), '')), '(o)', self._registered)
        except Exception:
            self._finish()

    def _call(self, path, interface, method, parameters, signature, completed):
        self._connection.call(NAME, path, interface, method, parameters,
            GLib.VariantType.new(signature), Gio.DBusCallFlags.NO_AUTO_START,
            750, None, completed)

    def _registered(self, connection, result):
        if self._closed:
            return
        try:
            self._client, = connection.call_finish(result).unpack()
            self._subscription = connection.signal_subscribe(
                NAME, CLIENT, None, self._client, None, Gio.DBusSignalFlags.NONE,
                self._signal)
            # Keep this client alive to acknowledge QueryEndSession. Exiting
            # first leaves a clientless manager waiting for its one-second
            # query timer before it can return the display to GDM.
            self._call(PATH, NAME, 'Logout', GLib.Variant('(u)', (2,)),
                       '()', self._reply)
        except Exception:
            self._finish()

    def _signal(self, _connection, _sender, _path, _interface, signal, _parameters):
        if self._closed:
            return
        if signal in ('Stop', 'CancelEndSession'):
            self._finish()
        elif signal in ('QueryEndSession', 'EndSession'):
            try:
                self._call(self._client, CLIENT, 'EndSessionResponse',
                           GLib.Variant('(bs)', (True, '')), '()', self._reply)
            except Exception:
                self._finish()

    def _reply(self, connection, result):
        if not self._closed:
            try:
                connection.call_finish(result)
            except Exception:
                self._finish()

    def _expired(self):
        self._deadline = 0
        self._finish()
        return GLib.SOURCE_REMOVE

    def _finish(self):
        if not self._closed:
            self.close()
            self._application.quit()

    def close(self):
        self._closed = True
        if self._subscription:
            self._connection.signal_unsubscribe(self._subscription)
            self._subscription = 0
        if self._deadline:
            GLib.source_remove(self._deadline)
            self._deadline = 0
