"""Embeddable, read-only host UI worker viewer for tools/watch."""

from common.oh_no_parent_control_ui.gtk_automation import set_automation_id as identify
from ui_watch_transport import Feeds, label

WAITING = 'Waiting for UI tests. You can leave this window open.'


def panel(feeds=None, *, prefix='', flat=False):
    def set_automation_id(widget, name):
        identify(widget, prefix + name)
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, GLib, Gtk, Pango

    class View(Gtk.Box):
        def __init__(self, identity):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                             hexpand=True, vexpand=True)
            set_automation_id(self, identity)
            self.picture = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.CONTAIN,
                                       hexpand=True, vexpand=True, focusable=False)
            set_automation_id(self.picture, identity + '-display')
            self.description = Gtk.Label(xalign=0, wrap=True, lines=2,
                                        ellipsize=Pango.EllipsizeMode.MIDDLE)
            set_automation_id(self.description, identity + '-test')
            self.state = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
            set_automation_id(self.state, identity + '-status')
            self.append(self.description)
            self.append(self.picture)
            self.append(self.state)
            self.sequence = None
            for side in ('start', 'end', 'top', 'bottom'):
                getattr(self, 'set_margin_' + side)(6)

        def update(self, frame):
            if frame[0] == self.sequence:
                return
            self.sequence = frame[0]
            meta = frame[1]
            texture = None
            if meta['state'] == 'live':
                texture = Gdk.MemoryTexture.new(meta['width'], meta['height'],
                    Gdk.MemoryFormat.B8G8R8X8, GLib.Bytes.new(frame[2]), meta['stride'])
            self.picture.set_paintable(texture)
            self.description.set_label(label(meta.get('test', '')) or 'Preparing UI worker')
            state = 'Live' if meta['state'] == 'live' else label(meta.get('detail', 'Waiting for frames'))
            self.state.set_label(f"{label(meta.get('phase', ''), 32)} · {state} · View only")

    class Panel(Gtk.Box):
        def __init__(self):
            super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
            self.feeds = feeds if feeds is not None else Feeds()
            self.views = {}
            self.selected_run = None
            self.active = False
            self.tab_bar = Gtk.Box(spacing=2)
            self.tab_bar.add_css_class('linked')
            set_automation_id(self.tab_bar, 'ui-watch-tabs')
            self.tabs = Gtk.Stack(hexpand=True, vexpand=True)
            set_automation_id(self.tabs, 'ui-watch-pages')
            self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True,
                                 hexpand=True, vexpand=True)
            set_automation_id(self.grid, 'ui-watch-grid')
            self.tabs.add_named(self.grid, 'all')
            self.all_tab = Gtk.ToggleButton(label='All branches', active=True)
            set_automation_id(self.all_tab, 'ui-watch-all-tab')
            self.all_tab.connect('toggled', self.select, self.grid)
            self.tab_bar.append(self.all_tab)
            self.status = Gtk.Label(label=WAITING, xalign=0, margin_start=8,
                margin_top=6, margin_bottom=6, ellipsize=Pango.EllipsizeMode.END)
            set_automation_id(self.status, 'ui-watch-status')
            if not flat:
                self.append(self.tab_bar)
                self.append(self.tabs)
                self.append(self.status)

        def select(self, button, page):
            if button.get_active():
                self.tabs.set_visible_child(page)

        def select_on_double_click(self, _gesture, count, _x, _y, tab):
            if count == 2:
                tab.set_active(True)

        def tick(self, *, render=True):
            selected = (self.selected_run or 'all') if flat else self.tabs.get_visible_child_name()
            frames = self.feeds.poll(pixels=render,
                                     selected=None if selected == 'all' else selected)
            self.active = bool(frames)
            if not render and not flat:
                return
            changed = False
            for run in tuple(self.views):
                if run not in frames:
                    overview, detail, tab = self.views.pop(run)
                    if tab.get_active():
                        self.all_tab.set_active(True)
                    if not flat:
                        self.grid.remove(overview)
                        self.tabs.remove(detail)
                        self.tab_bar.remove(tab)
                    changed = True
            for run, frame in frames.items():
                if run not in self.views:
                    overview = View('ui-watch-grid-' + run)
                    detail = overview if flat else View('ui-watch-branch-' + run)
                    name = label(frame[1].get('branch', ''), 120)
                    tab = Gtk.ToggleButton(label=name or f"Worker {frame[1].get('worker', run[:6])}")
                    set_automation_id(tab, 'ui-watch-tab-' + run)
                    tab.set_group(self.all_tab)
                    if not flat:
                        self.tabs.add_named(detail, run)
                        tab.connect('toggled', self.select, detail)
                        double_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
                        double_click.connect('pressed', self.select_on_double_click, tab)
                        overview.add_controller(double_click)
                        self.tab_bar.append(tab)
                    self.views[run] = [overview, detail, tab]
                    changed = True
                overview, detail, _tab = self.views[run]
                if render and selected == 'all':
                    overview.update(frame)
                elif render and selected == run:
                    detail.update(frame)
            if changed and not flat:
                for index, (overview, *_rest) in enumerate(self.views.values()):
                    if overview.get_parent() is not None:
                        self.grid.remove(overview)
                    self.grid.attach(overview, index % 2, index // 2, 1, 1)
            count = len(self.views)
            self.status.set_label(f'{count} active UI worker(s) · View only' if count else WAITING)

        def close(self):
            self.feeds.close()

    return Panel()
