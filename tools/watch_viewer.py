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


def viewer_entries(entries, *, scope='all', vm_ids=None):
    """Keep checkout UI workers, followed by one source per VM in ID order."""
    result, vms = {}, {}
    for entry, value in entries.items():
        if scope != 'all' and entry[0] != scope:
            continue
        if entry[1].startswith('ui-'):
            result[entry] = value
            continue
        previous = vms.get(entry[1])
        # Prefer the current controller, then a running unlocked display, over
        # an idle registration from another checkout. Ties keep discovery order.
        if previous is None or (value[3], value[2]) > (previous[1][3], previous[1][2]):
            vms[entry[1]] = entry, value
    ids = vm_ids or {}
    for entry, value in sorted(vms.values(), key=lambda item: (
            ids.get(item[0]) is None, int(ids.get(item[0]) or 0))):
        result[entry] = value
    return result


def panel(root, *, feeds=None, feed=None, output=None, vm_feeds=None, prefix=''):
    from vm_selection import registry
    from e2e_watch_viewer import AsyncFeed, Feed
    asynchronous = vm_feeds is None and feed is None
    configured = registry(root / 'config/test-vm.json') if asynchronous else {}
    if vm_feeds is None:
        vm_feeds = ({feed.vm_name: feed} if feed is not None else
                    {name: Feed(name, root=root) for name in configured})
    application_id = APPLICATION_ID
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    try:
        gi.require_version('Vte', '3.91')
    except ValueError as error:
        raise RuntimeError('watch needs GTK 4 VTE; run ./setup.sh --test-tools-only') from error
    from gi.repository import Gdk, GLib, Gtk, Pango, Vte
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
            self.next_ui = self.next_discovery = self.next_output = 0
            self.next_vm = {}
            self.output_active = False
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
            self.append(self.output_status)
            self.append(self.output_scroll)
            self.vm_keys = {name: 'vm-' + name.encode('ascii').hex() for name in vm_feeds}
            self.vm_ids = {self.vm_keys[name]: vm.id for name, vm in configured.items()}
            from ui_watch_transport import Feeds
            self.ui = ui_panel(feeds if feeds is not None else Feeds(root=root), prefix=prefix, flat=True)
            self.vms = {}
            for name, source in vm_feeds.items():
                key = self.vm_keys[name]
                if asynchronous:
                    source = AsyncFeed(source)
                vm_prefix = prefix + ('e2e-watch' if feed is not None else 'e2e-watch-' + key)
                view = vm_panel(source, vm_name=name, identity_prefix=vm_prefix)
                self.vms[key] = view
                self.next_vm[key] = 0
            # A single-feed fixture can exercise the shared panel in isolation.
            if feed is not None:
                self.vm = next(iter(self.vms.values()))

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

        def tick(self, *, render=True):
            now = time.monotonic()
            discover = now >= self.next_discovery
            if discover:
                self.next_discovery = now + .5
            # Hidden panels only inspect metadata twice a second. They never
            # copy pixels, create textures or redraw their widgets.
            ui_visible = render and (self.selected == 'all' or self.selected.startswith('ui-'))
            self.ui.selected_run = self.selected[3:] if self.selected.startswith('ui-') else None
            if (ui_visible and now >= self.next_ui) or (not ui_visible and discover):
                self.ui.tick(render=ui_visible)
                self.next_ui = now + .1
            for key, view in self.vms.items():
                vm_visible = render and self.selected in ('all', key)
                if ((vm_visible and now >= self.next_vm[key]) or
                        (not vm_visible and discover)):
                    view.tick(render=vm_visible)
                    self.next_vm[key] = now + (.1 if self.selected == 'all' else 1 / 30)
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
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango
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
            self.scopes = {}
            self.cells = {}
            self.viewer_layout = None
            self.terminal_layout = None
            self.syncing = False
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
            self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True,
                                  hexpand=True, vexpand=True)
            set_automation_id(self.pane, 'watch-columns')
            self.pane.set_shrink_start_child(True)
            self.pane.set_shrink_end_child(True)
            self.terminal_grid = Gtk.Grid(row_homogeneous=True, hexpand=True, vexpand=True)
            set_automation_id(self.terminal_grid, 'watch-terminal-grid')
            self.terminal_waiting = Gtk.Label(label='Waiting for terminal activity.',
                                             hexpand=True, vexpand=True)
            set_automation_id(self.terminal_waiting, 'watch-terminal-waiting')
            self.pane.set_start_child(self.terminal_grid)
            self.pane.set_end_child(self.checkout_pages)
            self.pane.add_tick_callback(self.initial_columns)
            self.add_scope('all', 'watch-all-')
            self.checkout_bar = Gtk.Box(spacing=2)
            self.checkout_bar.add_css_class('linked')
            set_automation_id(self.checkout_bar, 'watch-checkout-tabs')
            all_tab = Gtk.ToggleButton(label='All')
            set_automation_id(all_tab, 'watch-checkout-tab-all')
            self.checkout_buttons['all'] = all_tab
            all_tab.connect('toggled', self.select_checkout, 'all')
            self.checkout_bar.append(all_tab)
            body.append(self.pane)
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

        def initial_columns(self, widget, _clock):
            if widget.get_width() <= 1:
                return True
            widget.set_position(round(widget.get_width() * .25))
            return False

        def add_scope(self, name, prefix):
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            if name != 'all':
                set_automation_id(page, 'watch-checkout-page-' + identity(Path(name)))
            bar = Gtk.Box(spacing=2)
            bar.add_css_class('linked')
            set_automation_id(bar, prefix + 'watch-tabs')
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                       vscrollbar_policy=Gtk.PolicyType.NEVER)
            set_automation_id(scroll, prefix + 'watch-tabs-scroll')
            scroll.set_child(bar)
            pages = Gtk.Stack(hexpand=True, vexpand=True, hhomogeneous=False, vhomogeneous=False)
            set_automation_id(pages, prefix + 'watch-pages')
            grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True,
                            column_spacing=6, row_spacing=6, hexpand=True, vexpand=True)
            set_automation_id(grid, prefix + 'watch-viewer-grid')
            grid_scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True,
                hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            set_automation_id(grid_scroll, prefix + 'watch-viewer-scroll')
            grid_scroll.set_child(grid)
            pages.add_named(grid_scroll, 'all')
            blank = Gtk.Box(hexpand=True, vexpand=True)
            set_automation_id(blank, prefix + 'watch-empty-cell')
            waiting = Gtk.Label(label='Waiting for UI or VM activity.', wrap=True,
                                hexpand=True, vexpand=True)
            set_automation_id(waiting, prefix + 'watch-waiting')
            button = Gtk.ToggleButton(label='All')
            set_automation_id(button, prefix + 'watch-tab-all')
            bar.append(button)
            scope = dict(prefix=prefix, bar=bar, pages=pages, grid=grid, blank=blank,
                         waiting=waiting, buttons={'all': button}, bodies={}, selected='all')
            self.scopes[name] = scope
            button.connect('toggled', self.select_viewer, name, 'all')
            button.set_active(True)
            page.append(scroll)
            page.append(pages)
            self.checkout_pages.add_named(page, name)
            self.checkout_bodies[name] = page
            return scope

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
            weight = Pango.AttrList()
            weight.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
            view.heading.get_child().set_attributes(weight)
            view.heading.connect('clicked', lambda *_: self.checkout_buttons[name].set_active(True))
            set_automation_id(view.heading, 'watch-checkout-heading-' + key)
            view.prepend(view.heading)
            set_automation_id(view, 'watch-checkout-cell-' + key)
            scope = self.add_scope(name, prefix)
            view.buttons = scope['buttons']
            view.pages = scope['pages']
            view.vm_grid = scope['grid']
            view.pane = self.pane
            button = Gtk.ToggleButton(label=label, tooltip_text=name)
            set_automation_id(button, 'watch-checkout-tab-' + key)
            button.set_group(self.checkout_buttons['all'])
            button.connect('toggled', self.select_checkout, name)
            self.checkout_bar.append(button)
            self.checkouts[name] = view
            self.checkout_buttons[name] = button
            if len(self.checkouts) == 1:
                self.primary = view
                self.last_checkout = name

        def select_checkout(self, button, name):
            if button.get_active():
                self.selected_checkout = name
                self.checkout_pages.set_visible_child_name(name)
                self.arrange_checkouts()

        def select_viewer(self, button, scope_name, key):
            if button.get_active():
                self.scopes[scope_name]['selected'] = key
                for view in self.checkouts.values():
                    view.next_ui = view.next_discovery = 0
                    view.next_vm = dict.fromkeys(view.next_vm, 0)
                if self.checkout_buttons and not self.syncing:
                    self.arrange_checkouts()

        def cell_pressed(self, gesture, presses, _x, _y, entry):
            if presses == 2:
                scope_name = self.selected_checkout
                key = self.entry_key(scope_name, entry)
                self.scopes[scope_name]['buttons'][key].set_active(True)
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)

        def entry_key(self, scope_name, entry):
            name, local = entry
            return (identity(Path(name)) + '-' + local
                    if scope_name == 'all' and local.startswith('ui-') else local)

        def scoped_entries(self, scope_name, entries):
            ids = {(name, key): identifier for name, view in self.checkouts.items()
                   for key, identifier in view.vm_ids.items()}
            return viewer_entries(entries, scope=scope_name, vm_ids=ids)

        def entries(self):
            result = {}
            for name, view in self.checkouts.items():
                for run, (content, _detail, tab) in sorted(
                        view.ui.views.items(), key=lambda item: (item[1][2].get_label(), item[0])):
                    result[name, 'ui-' + run] = (content, 'UI - ' + tab.get_label(), True, True)
                for vm, key in view.vm_keys.items():
                    content = view.vms[key]
                    result[name, key] = (content, vm, content.active, content.locked)
            return result

        def sync_viewers(self, entries):
            self.syncing = True
            for entry in tuple(self.cells):
                if entry not in entries:
                    cell, _title = self.cells.pop(entry)
                    if cell.get_parent() is not None:
                        cell.get_parent().remove(cell)
            for entry, (content, _label, _active, _locked) in entries.items():
                if entry not in self.cells:
                    name, local = entry
                    prefix = self.scopes[name]['prefix']
                    cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
                    set_automation_id(cell, prefix + 'watch-cell-' + local)
                    if local.startswith('ui-'):
                        title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                          margin_start=8, margin_top=6, margin_bottom=6)
                        title.add_css_class('heading')
                        set_automation_id(title, prefix + 'watch-cell-title-' + local)
                        cell.append(title)
                    else:
                        title = content.title
                    cell.append(content)
                    click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
                    click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                    click.connect('pressed', self.cell_pressed, entry)
                    cell.add_controller(click)
                    self.cells[entry] = cell, title
            for scope_name, scope in self.scopes.items():
                scoped = self.scoped_entries(scope_name, entries)
                wanted = {self.entry_key(scope_name, entry) for entry in scoped}
                for key in tuple(scope['bodies']):
                    if key not in wanted:
                        if scope['selected'] == key:
                            scope['buttons']['all'].set_active(True)
                        scope['bar'].remove(scope['buttons'].pop(key))
                        scope['pages'].remove(scope['bodies'].pop(key))
                previous = scope['buttons']['all']
                for entry, (_content, label, _active, locked) in scoped.items():
                    key = self.entry_key(scope_name, entry)
                    if scope_name == 'all' and entry[1].startswith('ui-'):
                        label = '[' + self.checkout_buttons[entry[0]].get_label() + ']: ' + label
                    if key not in scope['buttons']:
                        button = Gtk.ToggleButton()
                        set_automation_id(button, scope['prefix'] + 'watch-tab-' + key)
                        button.set_group(scope['buttons']['all'])
                        scope['buttons'][key] = button
                        scope['bar'].append(button)
                        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
                        set_automation_id(body, scope['prefix'] + 'watch-page-' + key)
                        scope['pages'].add_named(body, key)
                        scope['bodies'][key] = body
                        button.connect('toggled', self.select_viewer, scope_name, key)
                    button = scope['buttons'][key]
                    button.set_label(label)
                    button.set_opacity(1 if locked else .45)
                    if button.get_prev_sibling() != previous:
                        scope['bar'].reorder_child_after(button, previous)
                    previous = button
            self.syncing = False

        def arrange_checkouts(self):
            for name, view in self.checkouts.items():
                self.checkout_buttons[name].set_opacity(1 if view.active else .45)
            active = tuple(name for name, view in self.checkouts.items() if view.output_active)
            if not active and self.last_checkout is not None:
                active = (self.last_checkout,)
            terminals = active if self.selected_checkout == 'all' else (self.selected_checkout,)
            if terminals != self.terminal_layout:
                self.terminal_layout = terminals
                while self.terminal_grid.get_first_child() is not None:
                    self.terminal_grid.remove(self.terminal_grid.get_first_child())
                for row, name in enumerate(terminals):
                    self.terminal_grid.attach(self.checkouts[name], 0, row, 1, 1)
                if not terminals:
                    self.terminal_grid.attach(self.terminal_waiting, 0, 0, 1, 1)

            entries = self.entries()
            self.sync_viewers(entries)
            scope_name = self.selected_checkout
            scope = self.scopes[scope_name]
            selected = scope['selected']
            scope['pages'].set_visible_child_name(selected)
            scoped = self.scoped_entries(scope_name, entries)
            shown = tuple(entry for entry, value in scoped.items()
                          if (value[2] if selected == 'all' else
                               self.entry_key(scope_name, entry) == selected))
            for entry in shown:
                self.cells[entry][1].set_label(
                    scope['buttons'][self.entry_key(scope_name, entry)].get_label())
            layout = scope_name, selected, shown
            if layout == self.viewer_layout:
                return
            self.viewer_layout = layout
            for cell, _title in self.cells.values():
                if cell.get_parent() is not None:
                    cell.get_parent().remove(cell)
            for other in self.scopes.values():
                for widget in (other['blank'], other['waiting']):
                    if widget.get_parent() is not None:
                        widget.get_parent().remove(widget)
            if selected == 'all':
                for index, entry in enumerate(shown):
                    scope['grid'].attach(self.cells[entry][0], index % 2, index // 2, 1, 1)
                if len(shown) > 1 and len(shown) % 2:
                    scope['grid'].attach(scope['blank'], 1, len(shown) // 2, 1, 1)
                if not shown:
                    scope['grid'].attach(scope['waiting'], 0, 0, 1, 1)
            elif shown:
                scope['bodies'][selected].append(self.cells[shown[0]][0])

        def tick(self):
            if self.discovery is not None:
                discovered = self.discovery.poll()
                for root, label in (discovered or {}).items():
                    self.add_checkout(root, label)
            for name, view in self.checkouts.items():
                was_active = view.output_active
                scope = self.scopes[self.selected_checkout]
                selected = scope['selected']
                visible = self.selected_checkout in ('all', name)
                if selected != 'all' and self.selected_checkout == 'all':
                    if selected.startswith('vm-'):
                        scoped = self.scoped_entries('all', self.entries())
                        visible = (name, selected) in scoped
                    else:
                        own_prefix = identity(Path(name)) + '-'
                        visible = selected.startswith(own_prefix)
                        selected = selected[len(own_prefix):] if visible else 'all'
                view.selected = selected
                view.tick(render=visible)
                if was_active and not view.output_active:
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
