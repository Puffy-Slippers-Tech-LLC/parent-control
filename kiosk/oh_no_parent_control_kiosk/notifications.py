"""Session notification provider for the dedicated GNOME Kiosk compositor.

GNOME Kiosk's documented notification tag keeps this separate system banner
above fullscreen windows. The service is started only by our kiosk target;
ordinary child desktops retain their own notification provider.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.about import branding_asset_path
from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.application_ui import ApplicationUI, bind_ui


INTERFACE = 'org.freedesktop.Notifications'
OBJECT_PATH = '/org/freedesktop/Notifications'
XML = '''<node><interface name="org.freedesktop.Notifications">
<method name="Notify">
 <arg type="s" direction="in"/><arg type="u" direction="in"/>
 <arg type="s" direction="in"/><arg type="s" direction="in"/>
 <arg type="s" direction="in"/><arg type="as" direction="in"/>
 <arg type="a{sv}" direction="in"/><arg type="i" direction="in"/>
 <arg type="u" direction="out"/>
</method>
<method name="CloseNotification"><arg type="u" direction="in"/></method>
<method name="GetCapabilities"><arg type="as" direction="out"/></method>
<method name="GetServerInformation">
 <arg type="s" direction="out"/><arg type="s" direction="out"/>
 <arg type="s" direction="out"/><arg type="s" direction="out"/>
</method>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
</interface></node>'''


class NotificationApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.puffyslippers.OhNoParentControl.KioskNotifications')
        self._application_ui = ApplicationUI(self)
        self._banner = None
        self._timer = 0
        self._notification_id = 0
        self._sender = None
        self._serial = 0
        self._registration = 0
        self._name_owner = 0

    def do_dbus_register(self, connection, path):
        if not Gtk.Application.do_dbus_register(self, connection, path):
            return False
        self._application_ui.register(connection, path)
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        self._registration = connection.register_object(
            OBJECT_PATH, info.interfaces[0], self._method_call, None, None)
        return bool(self._registration)

    def do_dbus_unregister(self, connection, path):
        if self._registration:
            connection.unregister_object(self._registration)
            self._registration = 0
        self._application_ui.unregister(connection)
        Gtk.Application.do_dbus_unregister(self, connection, path)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()
        self._name_owner = Gio.bus_own_name_on_connection(
            self.get_dbus_connection(), INTERFACE, Gio.BusNameOwnerFlags.NONE,
            None, lambda *_: self.quit())
        css = Gtk.CssProvider()
        css.load_from_string('''window.kiosk-notification { background: transparent; }
            .kiosk-notification-card { background: #24313b; color: white;
            border: 1px solid #698b9f; border-radius: 8px; padding: 6px 10px; }
            .kiosk-notification label { font: 16px sans-serif; }
            .kiosk-notification button { background: transparent; color: white; }''')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css = css

    def do_activate(self):
        pass

    def do_shutdown(self):
        self._close(3)
        if self._name_owner:
            Gio.bus_unown_name(self._name_owner)
            self._name_owner = 0
        Gtk.Application.do_shutdown(self)

    def _method_call(self, connection, sender, path, interface, method, parameters, invocation):
        if method == 'GetCapabilities':
            invocation.return_value(GLib.Variant('(as)', (['body', 'body-markup', 'persistence'],)))
        elif method == 'GetServerInformation':
            invocation.return_value(GLib.Variant('(ssss)', (
                'Oh No! Parent Control Kiosk Notifications', 'Puffy Slippers', '1', '1.2')))
        elif method == 'CloseNotification':
            identity, = parameters.unpack()
            if identity == self._notification_id and sender == self._sender:
                self._close(3)
            invocation.return_value(None)
        elif method == 'Notify':
            app, replaces, icon, summary, body, actions, hints, timeout = parameters.unpack()
            # Bound input and storage. This provider owns one banner at a time,
            # reads only its packaged logo, and never logs user-written content.
            if (len(body) > 16384 or len(summary) > 4096 or actions or
                    hints.get('urgency', 1) not in (0, 1, 2)):
                invocation.return_dbus_error(INTERFACE + '.InvalidArgument', 'Invalid notification')
                return
            reuse = replaces == self._notification_id and sender == self._sender
            identity = self._notification_id if reuse else self._serial + 1
            self._close(3, emit=not reuse)
            self._serial = max(self._serial, identity)
            self._notification_id, self._sender = identity, sender
            self._show(summary, body, hints.get('urgency', 1))
            milliseconds = (0 if hints.get('urgency') == 2 else 5000) if timeout < 0 else timeout
            if milliseconds > 0:
                def expired():
                    self._timer = 0
                    self._close(1)
                    return GLib.SOURCE_REMOVE
                self._timer = GLib.timeout_add(min(milliseconds, 86400000), expired)
            invocation.return_value(GLib.Variant('(u)', (identity,)))

    def _show(self, summary, body, urgency):
        window = Gtk.ApplicationWindow(application=self, decorated=False, resizable=False,
                                       title='gnome-kiosk-notification',
                                       css_classes=['kiosk-notification'])
        set_automation_id(window, 'kiosk-system-notification')
        row = Gtk.Box(spacing=10, margin_top=8, margin_bottom=8,
                      margin_start=10, margin_end=10, halign=Gtk.Align.CENTER,
                      css_classes=['kiosk-notification-card'])
        row.append(Gtk.Image.new_from_gicon(Gio.FileIcon.new(
            Gio.File.new_for_path(str(branding_asset_path('app_logo.png'))))))
        row.get_first_child().set_pixel_size(20)
        message = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                            max_width_chars=50, xalign=0)
        # The freedesktop body is markup. Invalid markup is displayed literally.
        try:
            Pango.parse_markup(body, -1, '\x00')
            message.set_markup(body)
        except GLib.Error:
            message.set_text(body)
        if summary:
            message.set_text(summary + '\n' + message.get_text())
        set_automation_id(message, 'kiosk-system-notification-message')
        bind_ui(message, get_value=lambda: 'critical' if urgency == 2 else 'high' if urgency == 1 else 'low')
        row.append(message)
        close = Gtk.Button(icon_name='window-close-symbolic', valign=Gtk.Align.CENTER)
        describe_control(close, m.CLOSE, m.CLOSE, automation_id='kiosk-system-notification-close')
        close.connect('clicked', lambda *_: self._close(2))
        row.append(close)
        # Kiosk's notification tag anchors the surface at the monitor's top
        # left. Span that monitor with a transparent surface and center the
        # actual card inside it; Gtk.Window cannot position Wayland windows.
        strip = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        strip.append(row)
        window.set_child(strip)
        monitors = Gdk.Display.get_default().get_monitors()
        monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is not None:
            def resize(target, *_args):
                target.set_default_size(monitor.get_geometry().width, -1)
            resize(window)
            monitor.connect_object('notify::geometry', resize, window)
        window.connect('close-request', self._close_requested)
        self._banner = window
        window.present()

    def _close_requested(self, *_):
        self._close(2)
        return True

    def _close(self, reason, *, emit=True):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        if self._banner:
            self._banner.destroy()
            self._banner = None
        if self._notification_id:
            if emit:
                self.get_dbus_connection().emit_signal(None, OBJECT_PATH, INTERFACE,
                    'NotificationClosed', GLib.Variant('(uu)', (self._notification_id, reason)))
            self._notification_id = 0
            self._sender = None


if __name__ == '__main__':
    raise SystemExit(NotificationApplication().run(sys.argv))
