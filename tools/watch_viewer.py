"""One desktop watcher for launcher output, host UI workers and the test VM."""

from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

APPLICATION_ID = 'org.onpc.E2EWatch'
TITLE = 'Test watch'


def application(feeds=None, feed=None, output=None):
    import gi
    gi.require_version('Gtk', '4.0')
    try:
        gi.require_version('Vte', '3.91')
    except ValueError as error:
        raise RuntimeError('watch needs GTK 4 VTE; run ./setup.sh --test-tools-only') from error
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte
    from common.oh_no_parent_control_ui.gtk_automation import (
        add_identified_window_controls, set_automation_id,
    )
    from ui_watch_viewer import panel as ui_panel
    from e2e_watch_viewer import panel as vm_panel
    from watch_output import Output, terminal, TerminalWriter

    for name in ('GIO_LAUNCHED_DESKTOP_FILE', 'GIO_LAUNCHED_DESKTOP_FILE_PID',
                 'DESKTOP_STARTUP_ID', 'XDG_ACTIVATION_TOKEN'):
        os.environ.pop(name, None)
    GLib.set_prgname(APPLICATION_ID)
    GLib.set_application_name(TITLE)

    class Viewer(Gtk.Application):
        def __init__(self):
            # The repository has one pinned VM. Session-bus registration keeps
            # a single watcher across checkouts and concurrent launches.
            super().__init__(application_id=APPLICATION_ID,
                             flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
            self.window = None
            self.selected = 'active'
            self.layout = None
            self.next_ui = self.next_discovery = self.next_output = 0
            self.output_active = False
            self.split_initialized = False

        def do_activate(self):
            if self.window is not None:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title=TITLE)
            set_automation_id(self.window, 'watch-window')
            self.window.set_icon_name(APPLICATION_ID)
            self.window.set_default_size(1400, 900)
            header = Gtk.HeaderBar()
            add_identified_window_controls(header, 'watch-window-controls')
            header.pack_start(Gtk.Image(
                icon_name=APPLICATION_ID, pixel_size=32, valign=Gtk.Align.CENTER))
            close = Gtk.Button(icon_name='window-close-symbolic', tooltip_text='Close viewer')
            close.update_property([Gtk.AccessibleProperty.LABEL], ['Close viewer'])
            set_automation_id(close, 'watch-close')
            close.connect('clicked', lambda *_: self.window.close())
            header.pack_end(close)
            self.window.set_titlebar(header)

            self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
            set_automation_id(self.pane, 'watch-columns')
            self.pane.set_shrink_start_child(True)
            self.pane.set_shrink_end_child(True)
            left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.output_status = Gtk.Label(label='Terminal Outputs — Waiting for tests',
                xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                margin_start=8, margin_end=8, margin_top=8, margin_bottom=8)
            set_automation_id(self.output_status, 'watch-output-status')
            self.terminal, self.output_scroll = terminal('watch-output', 'Test runner terminal output')
            self.writer = TerminalWriter(self.terminal)
            self.output = output if output is not None else Output(terminal_size=lambda: os.terminal_size((
                max(1, self.terminal.get_column_count()), max(1, self.terminal.get_row_count()))))
            if output is None:
                scrolling = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
                scrolling.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                def scroll_output(controller, dx, dy):
                    self.output.scroll(-round(dy * 3))
                    return True
                scrolling.connect('scroll', scroll_output)
                self.terminal.add_controller(scrolling)
            keys = Gtk.EventControllerKey()
            keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            keys.connect('key-pressed', self.terminal_key)
            self.terminal.add_controller(keys)
            context = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
            context.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            context.connect('pressed', self.terminal_context)
            self.terminal.add_controller(context)
            self.menu = Gtk.Popover(has_arrow=False)
            self.menu.set_parent(self.terminal)
            menu_items = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            for identity, label, action in (('watch-copy', 'Copy', self.copy_selection),
                                            ('watch-select-all', 'Select All', self.select_output),
                                            ('watch-stop', 'Stop command', self.stop_command)):
                button = Gtk.Button(label=label)
                set_automation_id(button, identity)
                button.add_css_class('flat')
                button.connect('clicked', lambda _button, callback=action: (callback(), self.menu.popdown()))
                menu_items.append(button)
            self.menu.set_child(menu_items)
            left.append(self.output_status)
            left.append(self.output_scroll)
            self.pane.set_start_child(left)

            right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bar = Gtk.Box(spacing=2)
            set_automation_id(bar, 'watch-tabs')
            bar.add_css_class('linked')
            self.buttons = {}
            self.pages = Gtk.Stack(hexpand=True, vexpand=True,
                                   hhomogeneous=False, vhomogeneous=False)
            set_automation_id(self.pages, 'watch-pages')
            self.bodies = {}
            for name, label in (('active', 'Active'), ('ui', 'UI'), ('vm', 'VM')):
                button = Gtk.ToggleButton(label=label)
                set_automation_id(button, 'watch-tab-' + name)
                if self.buttons:
                    button.set_group(self.buttons['active'])
                self.buttons[name] = button
                bar.append(button)
                body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
                set_automation_id(body, 'watch-page-' + name)
                self.pages.add_named(body, name)
                self.bodies[name] = body
                button.connect('toggled', self.select, name)
            self.ui, self.vm = ui_panel(feeds), vm_panel(feed)
            self.split = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, wide_handle=True,
                                   hexpand=True, vexpand=True)
            set_automation_id(self.split, 'watch-active-split')
            self.split.set_shrink_start_child(True)
            self.split.set_shrink_end_child(True)
            self.waiting = Gtk.Label(label='Waiting for UI or VM activity.', wrap=True,
                                     hexpand=True, vexpand=True)
            set_automation_id(self.waiting, 'watch-waiting')
            self.buttons['active'].set_active(True)
            self.arrange()
            right.append(bar)
            right.append(self.pages)
            self.pane.set_end_child(right)
            self.window.set_child(self.pane)
            self.pane.add_tick_callback(self.initial_columns)
            self.window.present()
            self.timer = GLib.timeout_add(33, self.tick)

        def initial_columns(self, widget, _clock):
            if widget.get_width() <= 1:
                return True
            widget.set_position(round(widget.get_width() * .3))
            return False

        def copy_selection(self):
            if self.terminal.get_has_selection():
                self.terminal.copy_clipboard_format(Vte.Format.TEXT)

        def select_output(self):
            self.terminal.select_all()

        def stop_command(self):
            self.output.cancel()

        def terminal_key(self, _controller, keyval, _keycode, state):
            control = bool(state & Gdk.ModifierType.CONTROL_MASK)
            shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
            if control and keyval in (Gdk.KEY_c, Gdk.KEY_C):
                self.copy_selection() if shift else self.stop_command()
                return True
            if control and shift and keyval in (Gdk.KEY_a, Gdk.KEY_A):
                self.select_output()
                return True
            return False

        def terminal_context(self, gesture, _presses, x, y):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            rectangle = Gdk.Rectangle()
            rectangle.x, rectangle.y = int(x), int(y)
            rectangle.width = rectangle.height = 1
            self.menu.set_pointing_to(rectangle)
            self.menu.popup()

        def initial_rows(self, widget, _clock):
            if widget.get_height() <= 1:
                return True
            widget.set_position(round(widget.get_height() * .5))
            return False

        def select(self, button, name):
            if button.get_active():
                self.selected = name
                self.next_ui = self.next_discovery = 0
                self.pages.set_visible_child_name(name)
                if hasattr(self, 'ui'):
                    self.arrange()

        def arrange(self):
            shown = ((self.ui.active, self.vm.active) if self.selected == 'active'
                     else (self.selected == 'ui', self.selected == 'vm'))
            layout = self.selected, shown
            if layout == self.layout:
                return
            self.layout = layout
            self.split.set_start_child(None)
            self.split.set_end_child(None)
            for body in self.bodies.values():
                while body.get_first_child() is not None:
                    body.remove(body.get_first_child())
            body = self.bodies[self.selected]
            if all(shown):
                self.split.set_start_child(self.ui)
                self.split.set_end_child(self.vm)
                body.append(self.split)
                if not self.split_initialized:
                    self.split_initialized = True
                    self.split.add_tick_callback(self.initial_rows)
            elif shown[0]:
                body.append(self.ui)
            elif shown[1]:
                body.append(self.vm)
            else:
                body.append(self.waiting)

        def tick(self):
            now = time.monotonic()
            discover = now >= self.next_discovery
            if discover:
                self.next_discovery = now + .5
            # Hidden panels only inspect metadata twice a second. They never
            # copy pixels, create textures, redraw widgets or query VM output.
            ui_visible = self.selected in ('active', 'ui')
            vm_visible = self.selected in ('active', 'vm')
            if (ui_visible and now >= self.next_ui) or (not ui_visible and discover):
                self.ui.tick(render=ui_visible)
                self.next_ui = now + .1
            if vm_visible or discover:
                self.vm.tick(render=vm_visible)
            label = ('Active - UI + VM' if self.ui.active and self.vm.active else
                     'Active - UI' if self.ui.active else 'Active- VM' if self.vm.active else 'Active')
            if self.buttons['active'].get_label() != label:
                self.buttons['active'].set_label(label)
            self.arrange()
            if now >= self.next_output:
                self.next_output = now + .2
                if not self.terminal.get_has_selection():
                    label, active, reset, data = self.output.poll()
                    self.writer.feed(data, reset=reset)
                    self.output_active = active
                else:
                    label, active = self.output.label, self.output_active
                text = ('Terminal Outputs — ' + label + ('' if active else ' (finished)')
                        if label else 'Terminal Outputs — Waiting for tests')
                if self.output_status.get_label() != text:
                    self.output_status.set_label(text)
            return True

        def do_shutdown(self):
            if hasattr(self, 'timer'):
                GLib.source_remove(self.timer)
                self.ui.close()
                self.vm.close()
                self.menu.unparent()
            Gtk.Application.do_shutdown(self)

    return Viewer()


def run_viewer():
    """Keep native GTK diagnostics out of the caller's active terminal."""
    from test_retention import allocate
    directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-watch-viewer-'))
    log_path = directory / 'viewer.log'
    print(f'Viewer diagnostics: {log_path}', flush=True)
    with log_path.open('x', encoding='utf-8') as log:
        sys.stdout.flush()
        sys.stderr.flush()
        stdout = os.dup(1)
        try:
            stderr = os.dup(2)
            try:
                os.dup2(log.fileno(), 1)
                os.dup2(log.fileno(), 2)
                with redirect_stdout(log), redirect_stderr(log):
                    try:
                        return application().run(['watch'])
                    finally:
                        sys.stdout.flush()
                        sys.stderr.flush()
            finally:
                os.dup2(stderr, 2)
                os.close(stderr)
        finally:
            os.dup2(stdout, 1)
            os.close(stdout)


def desktop_launch_command():
    """Launch from the desktop user manager, without an editor's Snap label."""
    command = ['/usr/bin/systemd-run', '--user', '--quiet', '--collect',
               '--service-type=exec']
    for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY',
                 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:
            command.append('--setenv=' + name + '=' + os.environ[name])
    return command + ['--', str(Path(__file__).resolve().with_name('watch')), '--desktop-session']


def main(argv=None):
    import argparse
    from e2e_watch_protocol import require
    parser = argparse.ArgumentParser(description='Watch test output, UI tests and VM activity.')
    parser.add_argument('--desktop-session', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require(os.getuid() != 0, 'launch-as-your-desktop-user')
    try:
        snap = Path('/proc/self/attr/current').read_text().startswith('snap.')
    except FileNotFoundError:
        snap = False
    if args.desktop_session:
        require(not snap, 'desktop-session-still-has-snap-identity')
        return run_viewer()
    # Type=exec confirms startup, then systemd-run returns. No inherited PTY,
    # wait or pipe keeps the caller's terminal attached to the viewer lifetime.
    return subprocess.run(desktop_launch_command(), check=False).returncode
