"""Session notification provider for the dedicated GNOME Kiosk compositor.

GNOME Kiosk's documented notification tag keeps this separate system banner
above fullscreen windows. The service is started only by our kiosk target;
ordinary child desktops retain their own notification provider.
"""

from pathlib import Path
import math
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
from common.oh_no_parent_control_ui.translation_widgets import TranslationContext, set_text
# The installed service executes this file directly, without a package context.
from kiosk.oh_no_parent_control_kiosk.chrome import register_form_font


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
        self._deadline = None

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
        register_form_font()
        css.load_from_string('''window.kiosk-notification { background: transparent; }
            .kiosk-notification-card { background: transparent; color: #eeedf8;
            border: 12px solid transparent; border-radius: 0; padding: 2px 6px;
            border-image-source: url("FRAME"); border-image-slice: 32 fill; border-image-width: 32px; }
            .kiosk-notification label { font: 8.5px "Monocraft", "Ubuntu Mono", monospace; }
            .kiosk-notification .reminder-message { font-size: 15px; font-weight: bold; color: #83edff;
            text-shadow: 1px 1px #24305b; }
            .kiosk-notification .reminder-caption { font-size: 12px; color: #dddfef; }
            .kiosk-notification .reminder-time { font-size: 12px; color: #c0efff; min-width: 14px; }
            .kiosk-notification button { background: transparent; color: #eeedf8;
            border: 0; border-radius: 0; padding: 0; box-shadow: none; min-width: 50px; }
            .kiosk-notification button:hover, .kiosk-notification button:focus { background: #38304d; }
            .kiosk-notification .reminder-divider { background: #676280; min-width: 1px; }
            .kiosk-notification .reminder-track { border: 1px solid #483092;
            border-radius: 1px; padding: 1px; background: #111125; }
            .kiosk-notification progressbar trough { background: #181230; min-height: 9px; min-width: 0;
            border: 0; border-radius: 0; }
            .kiosk-notification progressbar progress { background: linear-gradient(#24efff, #02cde9);
            min-height: 9px; min-width: 0; border: 0; border-radius: 0; }
            .kiosk-notification.onpc-readable-script label { font-family: sans-serif; }
            '''.replace('FRAME', str(branding_asset_path('reminder-frame.svg'))))
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
            seconds = hints.get('x-onpc-remaining-seconds')
            language = hints.get('x-onpc-language', '')
            # Bound input and storage. This provider owns one banner at a time,
            # reads only its packaged logo, and never logs user-written content.
            if (len(body) > 16384 or len(summary) > 4096 or actions or
                    hints.get('urgency', 1) not in (0, 1, 2) or
                    (seconds is not None and (type(seconds) is not int or not 0 <= seconds <= 0xFFFFFFFF)) or
                    not isinstance(language, str) or len(language) > 32):
                invocation.return_dbus_error(INTERFACE + '.InvalidArgument', 'Invalid notification')
                return
            reuse = replaces == self._notification_id and sender == self._sender
            identity = self._notification_id if reuse else self._serial + 1
            self._close(3, emit=not reuse)
            self._serial = max(self._serial, identity)
            self._notification_id, self._sender = identity, sender
            milliseconds = ((5000 if seconds >= 60 else 0) if seconds is not None else
                            (0 if hints.get('urgency') == 2 else 5000) if timeout < 0 else timeout)
            self._show(summary, body, hints.get('urgency', 1), milliseconds, language)
            if milliseconds > 0:
                self._deadline = GLib.get_monotonic_time() + min(milliseconds, 86400000) * 1000
                if self._tick() == GLib.SOURCE_CONTINUE:
                    self._timer = GLib.timeout_add(50, self._tick)
            invocation.return_value(GLib.Variant('(u)', (identity,)))

    def _show(self, summary, body, urgency, milliseconds, language):
        window = Gtk.ApplicationWindow(application=self, decorated=False, resizable=False,
                                       title='gnome-kiosk-notification',
                                       css_classes=['kiosk-notification'])
        set_automation_id(window, 'kiosk-system-notification')
        window._translation_context = TranslationContext(language)
        row = Gtk.Box(spacing=11, margin_top=8, margin_bottom=8,
                      margin_start=8, margin_end=8, halign=Gtk.Align.CENTER,
                      css_classes=['kiosk-notification-card'])
        row.append(Gtk.Image.new_from_gicon(Gio.FileIcon.new(
            Gio.File.new_for_path(str(branding_asset_path('app_logo.png'))))))
        row.get_first_child().set_pixel_size(56)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          valign=Gtk.Align.CENTER, hexpand=True)
        message = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                            max_width_chars=20, xalign=0, css_classes=['reminder-message'])
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
        content.append(message)
        countdown = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                            visible=milliseconds > 0)
        caption = Gtk.Label(xalign=0, wrap=True, max_width_chars=42, css_classes=['reminder-caption'])
        set_text(caption, 'label', m.REMINDER_AUTO_CLOSE)
        countdown.append(caption)
        progress_row = Gtk.Box(spacing=8, margin_end=17)
        self._progress = Gtk.Box(spacing=3, hexpand=True, valign=Gtk.Align.CENTER,
                                 css_classes=['reminder-track'])
        self._segments = []
        for index in range(5):
            segment = Gtk.ProgressBar(hexpand=True)
            set_automation_id(segment, f'kiosk-system-notification-progress-{index}')
            self._segments.append(segment)
            self._progress.append(segment)
        self._countdown_label = Gtk.Label(css_classes=['reminder-time'])
        set_automation_id(self._countdown_label, 'kiosk-system-notification-countdown')
        progress_row.append(self._progress)
        progress_row.append(self._countdown_label)
        countdown.append(progress_row)
        content.append(countdown)
        row.append(content)
        row.append(Gtk.Box(width_request=1, margin_top=5, margin_bottom=5,
                           margin_start=3, margin_end=4,
                           css_classes=['reminder-divider']))
        action_row = Gtk.Box(spacing=11, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        row.append(action_row)
        for identity, filename, label, callback in (
                ('preferences', 'reminder-preferences.svg', m.PREFERENCES, self._preferences),
                ('close', 'reminder-dismiss.svg', m.DISMISS, lambda *_: self._close(2))):
            image = Gtk.Image.new_from_file(str(branding_asset_path(filename)))
            image.set_halign(Gtk.Align.CENTER)
            image.set_pixel_size(40)
            button = Gtk.Button(child=image, valign=Gtk.Align.CENTER)
            set_text(button, 'tooltip-text', label)
            describe_control(button, label, label, automation_id=f'kiosk-system-notification-{identity}')
            button.connect('clicked', callback)
            action_row.append(button)
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

    def _tick(self):
        left = max(0, (self._deadline - GLib.get_monotonic_time()) / 1000000)
        if left == 0:
            self._timer = 0
            self._close(1)
            return GLib.SOURCE_REMOVE
        for index, segment in enumerate(self._segments):
            segment.set_fraction(1 if index < math.ceil(left) else 0)
        set_text(self._countdown_label, 'label', m.COMPACT_SECONDS % {'count': math.ceil(left)})
        return GLib.SOURCE_CONTINUE

    def _preferences(self, *_args):
        self._close(2)
        def activated(connection, result):
            try:
                connection.call_finish(result)
            except GLib.Error:
                pass
        self.get_dbus_connection().call(
            'com.puffyslippers.OhNoParentControl', '/com/puffyslippers/OhNoParentControl',
            'org.gtk.Actions', 'Activate', GLib.Variant('(sava{sv})', ('preferences', [], {})),
            None, Gio.DBusCallFlags.NONE, 5000, None, activated)

    def _close_requested(self, *_):
        self._close(2)
        return True

    def _close(self, reason, *, emit=True):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self._deadline = None
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
