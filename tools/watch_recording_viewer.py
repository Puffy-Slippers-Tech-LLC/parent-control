"""Private GTK renderer for runner-owned watch recordings."""

from pathlib import Path
import time

from watch_model import viewer_entries

APPLICATION_ID = 'org.onpc.WatchRecording'
TITLE = 'Test recording'


def panel(root, *, prefix='', vm_names=None):
    from e2e_watch_viewer import AsyncFeed, Feed, panel as vm_panel
    from ui_watch_transport import Feeds
    from ui_watch_viewer import panel as ui_panel
    from vm_selection import registry
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk
    configured = registry(root / 'config/test-vm.json')
    if vm_names is not None:
        configured = {name: vm for name, vm in configured.items() if name in vm_names}

    class Viewer(Gtk.Box):
        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            self.root = root
            self.active = False
            self.selected = 'all'
            self.next_ui = self.next_discovery = 0
            self.next_vm = {}
            self.configured_vms = configured
            vm_feeds = {name: Feed(name, root=root) for name in configured}
            self.vm_keys = {name: 'vm-' + name.encode('ascii').hex() for name in vm_feeds}
            self.vm_ids = {self.vm_keys[name]: vm.id for name, vm in configured.items()}
            self.ui = ui_panel(Feeds(root=root), prefix=prefix, flat=True)
            self.vms = {}
            for name, source in vm_feeds.items():
                key = self.vm_keys[name]
                source = AsyncFeed(source)
                vm_prefix = prefix + 'e2e-watch-' + key
                view = vm_panel(source, vm_name=name, identity_prefix=vm_prefix)
                self.vms[key] = view
                self.next_vm[key] = 0

        def refresh_vms(self, configured):
            if vm_names is not None:
                configured = {name: vm for name, vm in configured.items() if name in vm_names}
            if configured == self.configured_vms:
                return
            for name in tuple(self.vm_keys):
                if name not in configured:
                    key = self.vm_keys.pop(name)
                    self.vms.pop(key).close()
                    self.next_vm.pop(key)
            for name in configured:
                if name not in self.vm_keys:
                    key = 'vm-' + name.encode('ascii').hex()
                    self.vm_keys[name] = key
                    source = AsyncFeed(Feed(name, root=self.root))
                    self.vms[key] = vm_panel(source, vm_name=name,
                        identity_prefix=prefix + 'e2e-watch-' + key)
                    self.next_vm[key] = 0
            self.vm_ids = {self.vm_keys[name]: vm.id for name, vm in configured.items()}
            self.configured_vms = configured

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
            self.active = self.ui.active or any(view.active for view in self.vms.values())
            return True

        def close(self):
            self.ui.close()
            for view in self.vms.values():
                view.close()

    return Viewer()


def application(*, checkouts, sources, tick_interval=200, window_size=(1280, 720)):
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango
    from common.oh_no_parent_control_ui.gtk_automation import (
        set_automation_id,
    )
    from watch_checkouts import identity

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.window = None
            self.selected_checkout = 'all'
            self.checkouts = {}
            self.branches = {}
            self.scopes = {}
            self.cells = {}
            self.viewer_layout = None
            self.syncing = False
            self.discovery = None

        def do_activate(self):
            if self.window is not None:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title=TITLE)
            set_automation_id(self.window, 'watch-window')
            self.window.set_default_size(*window_size)
            self.window.set_decorated(False)
            self.checkout_pages = Gtk.Stack(hexpand=True, vexpand=True,
                                           hhomogeneous=False, vhomogeneous=False)
            set_automation_id(self.checkout_pages, 'watch-checkout-pages')
            self.add_scope('all', 'watch-all-')
            self.window.set_child(self.checkout_pages)
            initial = checkouts
            for root, label in initial.items():
                options = (sources or {}).get(root, {})
                self.add_checkout(root, label, options)
            self.window.present()
            self.timer = GLib.timeout_add(tick_interval, self.tick)

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
            return scope

        def add_checkout(self, root, label, options=None, prefix=None):
            name = str(root)
            if name in self.checkouts:
                self.branches[name] = label
                self.checkouts[name].branch = label
                return
            key = identity(root)
            prefix = 'watch-checkout-' + key + '-' if prefix is None else prefix
            try:
                view = panel(root, prefix=prefix, **(options or {}))
            except (OSError, ValueError):
                return
            view.branch = label
            self.checkouts[name] = view
            self.branches[name] = label
            if len(self.checkouts) == 1:
                self.primary = view

        def select_viewer(self, button, scope_name, key):
            if button.get_active():
                self.scopes[scope_name]['selected'] = key
                for view in self.checkouts.values():
                    view.next_ui = view.next_discovery = 0
                    view.next_vm = dict.fromkeys(view.next_vm, 0)
                if self.checkouts and not self.syncing:
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
            primary = self.__dict__.get('primary')
            return viewer_entries(entries, scope=scope_name, vm_ids=ids,
                                  current_vms=set(primary.vm_keys.values()) if primary else set())

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
                    prefix = 'watch-checkout-' + identity(Path(name)) + '-'
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
                            scope['selected'] = 'all'
                            scope['buttons']['all'].set_active(True)
                        scope['bar'].remove(scope['buttons'].pop(key))
                        scope['pages'].remove(scope['bodies'].pop(key))
                previous = scope['buttons']['all']
                for entry, (_content, label, _active, locked) in scoped.items():
                    key = self.entry_key(scope_name, entry)
                    label = '[' + self.branches[entry[0]] + '] ' + label
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
                poll_vms = getattr(self.discovery, 'poll_vms', None)
                if poll_vms is not None:
                    for root, configured in (poll_vms() or {}).items():
                        view = self.checkouts.get(str(root))
                        if view is not None:
                            view.refresh_vms(configured)
            for name, view in self.checkouts.items():
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

    return Application()
