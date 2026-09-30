"""One desktop watcher for launcher output, host UI workers and all test VMs."""

from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

APPLICATION_ID = 'org.onpc.E2EWatch'
TITLE = 'Test watch'


def panel(root, *, feeds=None, feed=None, output=None, vm_feeds=None, prefix=''):
    from vm_selection import registry
    from e2e_watch_viewer import AsyncFeed, Feed
    asynchronous = vm_feeds is None and feed is None
    if vm_feeds is None:
        vm_feeds = ({feed.vm_name: feed} if feed is not None else
                    {name: Feed(name, root=root) for name in registry(root / 'config/test-vm.json')})
    application_id = APPLICATION_ID
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    try:
        gi.require_version('Vte', '3.91')
    except ValueError as error:
        raise RuntimeError('watch needs GTK 4 VTE; run ./setup.sh --test-tools-only') from error
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte
    from common.oh_no_parent_control_ui.gtk_automation import (
        set_automation_id as identify,
    )
    from ui_watch_viewer import panel as ui_panel
    from e2e_watch_viewer import panel as vm_panel
    from watch_output import Output, terminal, TerminalWriter

    def set_automation_id(widget, name):
        identify(widget, prefix + name)

    for name in ('GIO_LAUNCHED_DESKTOP_FILE', 'GIO_LAUNCHED_DESKTOP_FILE_PID',
                 'DESKTOP_STARTUP_ID', 'XDG_ACTIVATION_TOKEN'):
        os.environ.pop(name, None)
    GLib.set_prgname(application_id)
    GLib.set_application_name(TITLE)

    class Viewer(Gtk.Box):
        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            self.root = root
            self.active = False
            self.selected = 'all'
            self.layout = None
            self.grid_layout = None
            self.next_ui = self.next_discovery = self.next_output = 0
            self.next_vm = {}
            self.output_active = False
            self.split_initialized = False
            self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
            set_automation_id(self.pane, 'watch-columns')
            self.pane.set_shrink_start_child(True)
            self.pane.set_shrink_end_child(True)
            left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.output_status = Gtk.Label(label='Terminal Outputs — Waiting for tests',
                xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                margin_start=8, margin_end=8, margin_top=8, margin_bottom=8)
            set_automation_id(self.output_status, 'watch-output-status')
            self.terminal, self.output_scroll = terminal(prefix + 'watch-output', 'Test runner terminal output')
            self.writer = TerminalWriter(self.terminal)
            self.output = output if output is not None else Output(root, terminal_size=lambda: os.terminal_size((
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
            self.tab_bar = bar
            set_automation_id(bar, 'watch-tabs')
            bar.add_css_class('linked')
            self.buttons = {}
            self.pages = Gtk.Stack(hexpand=True, vexpand=True,
                                   hhomogeneous=False, vhomogeneous=False)
            set_automation_id(self.pages, 'watch-pages')
            self.bodies = {}
            self.vm_keys = {name: 'vm-' + name.encode('ascii').hex() for name in vm_feeds}
            for name, label in (('all', 'All'), ('ui', 'UI'),
                                *((key, name) for name, key in self.vm_keys.items())):
                button = Gtk.ToggleButton(label=label)
                set_automation_id(button, 'watch-tab-' + name)
                if self.buttons:
                    button.set_group(self.buttons['all'])
                self.buttons[name] = button
                bar.append(button)
                body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
                set_automation_id(body, 'watch-page-' + name)
                self.pages.add_named(body, name)
                self.bodies[name] = body
                button.connect('toggled', self.select, name)
            from ui_watch_transport import Feeds
            self.ui = ui_panel(feeds if feeds is not None else Feeds(root=root), prefix=prefix)
            self.vms = {}
            for name, source in vm_feeds.items():
                key = self.vm_keys[name]
                if asynchronous:
                    source = AsyncFeed(source)
                vm_prefix = prefix + ('e2e-watch' if feed is not None else 'e2e-watch-' + key)
                view = vm_panel(source, vm_name=name, identity_prefix=vm_prefix)
                self.vms[key] = view
                self.next_vm[key] = 0
                self.buttons[key].set_opacity(.45)
                click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
                click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                click.connect('pressed', self.vm_pressed, key)
                view.add_controller(click)
            # A single-feed fixture can exercise the shared panel in isolation.
            if feed is not None:
                self.vm = next(iter(self.vms.values()))
            self.vm_grid = Gtk.Grid(column_spacing=6, row_spacing=6,
                                    column_homogeneous=True, row_homogeneous=True,
                                    hexpand=True, vexpand=True)
            set_automation_id(self.vm_grid, 'watch-vm-grid')
            self.vm_blank = Gtk.Box(hexpand=True, vexpand=True)
            set_automation_id(self.vm_blank, 'watch-vm-empty-cell')
            self.split = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, wide_handle=True,
                                   hexpand=True, vexpand=True)
            set_automation_id(self.split, 'watch-active-split')
            self.split.set_shrink_start_child(True)
            self.split.set_shrink_end_child(True)
            self.waiting = Gtk.Label(label='Waiting for UI or VM activity.', wrap=True,
                                     hexpand=True, vexpand=True)
            set_automation_id(self.waiting, 'watch-waiting')
            self.buttons['all'].set_active(True)
            self.arrange()
            right.append(bar)
            right.append(self.pages)
            self.pane.set_end_child(right)
            self.append(self.pane)
            self.pane.add_tick_callback(self.initial_columns)

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

        def vm_pressed(self, gesture, presses, _x, _y, key):
            if presses == 2:
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
                self.buttons[key].set_active(True)

        def arrange(self):
            vm_keys = tuple(key for key, view in self.vms.items() if view.active)
            shown = self.ui.active if self.selected == 'all' else self.selected == 'ui'
            vm_shown = self.selected == 'all' and bool(vm_keys)
            layout = self.selected, shown, vm_shown
            if self.selected == 'all' and layout == self.layout:
                self.arrange_grid(vm_keys)
            if layout == self.layout:
                return
            self.layout = layout
            self.split.set_start_child(None)
            self.split.set_end_child(None)
            while self.vm_grid.get_first_child() is not None:
                self.vm_grid.remove(self.vm_grid.get_first_child())
            self.grid_layout = None
            for body in self.bodies.values():
                while body.get_first_child() is not None:
                    body.remove(body.get_first_child())
            body = self.bodies[self.selected]
            if self.selected in self.vms:
                body.append(self.vms[self.selected])
                return
            if self.selected == 'all':
                self.arrange_grid(vm_keys)
            if shown and vm_shown:
                self.split.set_start_child(self.ui)
                self.split.set_end_child(self.vm_grid)
                body.append(self.split)
                if not self.split_initialized:
                    self.split_initialized = True
                    self.split.add_tick_callback(self.initial_rows)
            elif shown:
                body.append(self.ui)
            elif vm_shown:
                body.append(self.vm_grid)
            else:
                body.append(self.waiting)

        def arrange_grid(self, vm_keys):
            if vm_keys == self.grid_layout:
                return
            self.grid_layout = vm_keys
            desired = {self.vms[key]: (index % 2, index // 2)
                       for index, key in enumerate(vm_keys)}
            if len(vm_keys) > 1 and len(vm_keys) % 2:
                desired[self.vm_blank] = (1, len(vm_keys) // 2)
            child = self.vm_grid.get_first_child()
            while child is not None:
                following = child.get_next_sibling()
                if child not in desired:
                    self.vm_grid.remove(child)
                child = following
            for child, (column, row) in desired.items():
                if child.get_parent() != self.vm_grid:
                    self.vm_grid.attach(child, column, row, 1, 1)
                else:
                    placement = self.vm_grid.get_layout_manager().get_layout_child(child)
                    placement.set_column(column)
                    placement.set_row(row)

        def tick(self, *, render=True):
            now = time.monotonic()
            discover = now >= self.next_discovery
            if discover:
                self.next_discovery = now + .5
            # Hidden panels only inspect metadata twice a second. They never
            # copy pixels, create textures or redraw their widgets.
            ui_visible = render and self.selected in ('all', 'ui')
            if (ui_visible and now >= self.next_ui) or (not ui_visible and discover):
                self.ui.tick(render=ui_visible)
                self.next_ui = now + .1
            for key, view in self.vms.items():
                vm_visible = render and self.selected in ('all', key)
                if ((vm_visible and now >= self.next_vm[key]) or
                        (not vm_visible and discover)):
                    view.tick(render=vm_visible)
                    self.next_vm[key] = now + (.1 if self.selected == 'all' else 1 / 30)
                    self.buttons[key].set_opacity(1 if view.locked else .45)
            self.arrange()
            if now >= self.next_output:
                self.next_output = now + .2
                if not self.terminal.get_has_selection():
                    label, active, reset, data = self.output.poll()
                    self.writer.feed(data, reset=reset)
                    self.output_active = active
                else:
                    run, _label = self.output.discover()
                    self.output_active = run is not None
                    label, active = self.output.label, self.output_active
                text = ('Terminal Outputs — ' + label + ('' if active else ' (finished)')
                        if label else 'Terminal Outputs — Waiting for tests')
                if self.output_status.get_label() != text:
                    self.output_status.set_label(text)
            self.active = self.output_active or self.ui.active or any(view.active for view in self.vms.values())
            return True

        def close(self):
            self.ui.close()
            for view in self.vms.values():
                view.close()
            self.menu.unparent()

    return Viewer()


def application(feeds=None, feed=None, output=None, vm_feeds=None, *, checkouts=None,
                discovery=None, sources=None):
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, Gio, GLib, Gtk
    from common.oh_no_parent_control_ui.gtk_automation import (
        add_identified_window_controls, set_automation_id,
    )
    from watch_checkouts import ROOT, Discovery, checkout, identity
    fixture = any(value is not None for value in (feeds, feed, output, vm_feeds))

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
            self.window = None
            self.selected_checkout = 'all'
            self.checkouts = {}
            self.checkout_buttons = {}
            self.checkout_bodies = {}
            self.checkout_layout = None
            self.last_checkout = None
            self.discovery = discovery

        def do_open(self, files, _count, _hint):
            self.activate()
            for file in files:
                try:
                    root = checkout(file.get_path())
                    if self.discovery is not None:
                        self.discovery.add(root)
                except (OSError, TypeError, ValueError):
                    continue

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
            header.pack_start(Gtk.Image(icon_name=APPLICATION_ID, pixel_size=32))
            close = Gtk.Button(icon_name='window-close-symbolic', tooltip_text='Close viewer')
            close.update_property([Gtk.AccessibleProperty.LABEL], ['Close viewer'])
            set_automation_id(close, 'watch-close')
            close.connect('clicked', lambda *_: self.window.close())
            header.pack_end(close)
            self.window.set_titlebar(header)
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.checkout_pages = Gtk.Stack(hexpand=True, vexpand=True,
                                           hhomogeneous=False, vhomogeneous=False)
            set_automation_id(self.checkout_pages, 'watch-checkout-pages')
            self.checkout_grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True,
                                          column_spacing=6, row_spacing=6,
                                          hexpand=True, vexpand=True)
            set_automation_id(self.checkout_grid, 'watch-checkout-grid')
            self.checkout_pages.add_named(self.checkout_grid, 'all')
            self.checkout_blank = Gtk.Box(hexpand=True, vexpand=True)
            set_automation_id(self.checkout_blank, 'watch-checkout-empty-cell')
            self.checkout_waiting = Gtk.Label(label='Waiting for checkout activity.',
                                             hexpand=True, vexpand=True)
            set_automation_id(self.checkout_waiting, 'watch-checkout-waiting')
            self.checkout_bar = Gtk.Box(spacing=2)
            self.checkout_bar.add_css_class('linked')
            set_automation_id(self.checkout_bar, 'watch-checkout-tabs')
            all_tab = Gtk.ToggleButton(label='All')
            set_automation_id(all_tab, 'watch-checkout-tab-all')
            self.checkout_buttons['all'] = all_tab
            all_tab.connect('toggled', self.select_checkout, 'all')
            self.checkout_bar.append(all_tab)
            body.append(self.checkout_pages)
            body.append(self.checkout_bar)
            self.window.set_child(body)
            initial = checkouts if checkouts is not None else {ROOT: ROOT.name}
            for index, (root, label) in enumerate(initial.items()):
                options = ((sources or {}).get(root) or
                           (dict(feeds=feeds, feed=feed, output=output, vm_feeds=vm_feeds)
                            if fixture and index == 0 else {}))
                self.add_checkout(root, label, options, prefix='' if fixture and index == 0 else None)
            if self.discovery is None and checkouts is None and not fixture:
                self.discovery = Discovery()
            all_tab.set_active(True)
            if fixture:
                # Existing single-panel probes exercise the exact same component.
                self.checkout_buttons[str(next(iter(initial)))].set_active(True)
            self.window.present()
            self.timer = GLib.timeout_add(33, self.tick)

        def add_checkout(self, root, label, options=None, prefix=None):
            name = str(root)
            if name in self.checkouts:
                self.checkout_buttons[name].set_label(label)
                self.checkouts[name].heading.set_label(label)
                return
            key = identity(root)
            prefix = 'watch-checkout-' + key + '-' if prefix is None else prefix
            try:
                view = panel(root, prefix=prefix, **(options or {}))
            except (OSError, ValueError):
                return
            view.heading = Gtk.Button(label=label)
            view.heading.add_css_class('flat')
            view.heading.connect('clicked', lambda *_: self.checkout_buttons[name].set_active(True))
            set_automation_id(view.heading, 'watch-checkout-heading-' + key)
            view.tab_bar.prepend(view.heading)
            set_automation_id(view, 'watch-checkout-cell-' + key)
            click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            click.connect('released', self.checkout_pressed, name)
            view.add_controller(click)
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            set_automation_id(page, 'watch-checkout-page-' + key)
            self.checkout_pages.add_named(page, name)
            button = Gtk.ToggleButton(label=label, tooltip_text=name)
            set_automation_id(button, 'watch-checkout-tab-' + key)
            button.set_group(self.checkout_buttons['all'])
            button.connect('toggled', self.select_checkout, name)
            self.checkout_bar.append(button)
            self.checkouts[name] = view
            self.checkout_buttons[name] = button
            self.checkout_bodies[name] = page
            if len(self.checkouts) == 1:
                self.primary = view
                self.last_checkout = name

        def select_checkout(self, button, name):
            if button.get_active():
                self.selected_checkout = name
                self.checkout_pages.set_visible_child_name(name)
                self.arrange_checkouts()

        def checkout_pressed(self, _gesture, _presses, _x, _y, name):
            if self.selected_checkout == 'all':
                self.checkout_buttons[name].set_active(True)

        def arrange_checkouts(self):
            for name, view in self.checkouts.items():
                self.checkout_buttons[name].set_opacity(1 if view.active else .45)
            active = tuple(name for name, view in self.checkouts.items() if view.active)
            if not active and self.last_checkout is not None:
                active = (self.last_checkout,)
            layout = self.selected_checkout, active
            if layout == self.checkout_layout:
                return
            self.checkout_layout = layout
            target = (self.checkout_grid if self.selected_checkout == 'all' else
                      self.checkout_bodies[self.selected_checkout])
            desired = ({self.checkouts[name]: (index % 2, index // 2)
                        for index, name in enumerate(active)} if self.selected_checkout == 'all' else
                       {self.checkouts[self.selected_checkout]: (0, 0)})
            if self.selected_checkout == 'all':
                if len(active) > 1 and len(active) % 2:
                    desired[self.checkout_blank] = (1, len(active) // 2)
                if not active:
                    desired[self.checkout_waiting] = (0, 0)
            for view in (*self.checkouts.values(), self.checkout_blank, self.checkout_waiting):
                parent = view.get_parent()
                if parent is not None and (view not in desired or parent != target):
                    parent.remove(view)
            for view, (column, row) in desired.items():
                if target == self.checkout_grid:
                    if view.get_parent() != target:
                        target.attach(view, column, row, 1, 1)
                    else:
                        placement = target.get_layout_manager().get_layout_child(view)
                        placement.set_column(column)
                        placement.set_row(row)
                elif view.get_parent() != target:
                    target.append(view)

        def tick(self):
            if self.discovery is not None:
                discovered = self.discovery.poll()
                for root, label in (discovered or {}).items():
                    self.add_checkout(root, label)
            for name, view in self.checkouts.items():
                was_active = view.active
                visible = (self.selected_checkout == name or
                           (self.selected_checkout == 'all' and view.get_parent() == self.checkout_grid))
                view.tick(render=visible)
                if was_active and not view.active:
                    self.last_checkout = name
            self.arrange_checkouts()
            return True

        def do_shutdown(self):
            if hasattr(self, 'timer'):
                GLib.source_remove(self.timer)
            for view in self.checkouts.values():
                view.close()
            if self.discovery is not None:
                self.discovery.close()
            Gtk.Application.do_shutdown(self)

        def __getattr__(self, name):
            # Compatibility for the existing isolated transport/panel probes.
            primary = self.__dict__.get('primary')
            if fixture and primary is not None:
                return getattr(primary, name)
            raise AttributeError(name)

    return Application()


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
                        return application().run(['watch', str(Path(__file__).resolve().parents[1])])
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
    parser = argparse.ArgumentParser(description='Watch test output, UI tests and VM activity.',
                                    epilog='Watches all registered VMs; no VM parameter is accepted.')
    parser.add_argument('--desktop-session', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    from vm_selection import registry
    try:
        registry()
    except ValueError as error:
        parser.error(str(error))
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
