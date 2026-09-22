"""Optional GTK spectator for concurrent host UI workers."""

from contextlib import redirect_stderr, redirect_stdout
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from common.oh_no_parent_control_ui.gtk_automation import (
    add_identified_window_controls, set_automation_id,
)
from ui_watch_transport import Feeds, label

APPLICATION_ID = 'org.onpc.UIWatch'
TITLE = 'UI tests — View only'
WAITING = 'Waiting for UI tests. You can leave this window open.'


def application(feeds=None):
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango

    for name in ('GIO_LAUNCHED_DESKTOP_FILE', 'GIO_LAUNCHED_DESKTOP_FILE_PID',
                 'DESKTOP_STARTUP_ID', 'XDG_ACTIVATION_TOKEN'):
        os.environ.pop(name, None)
    GLib.set_prgname(APPLICATION_ID)
    GLib.set_application_name(TITLE)

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
            for side in ('start', 'end', 'top', 'bottom'):
                getattr(self, 'set_margin_' + side)(6)

        def update(self, frame, texture):
            meta = frame[1]
            self.picture.set_paintable(texture)
            self.description.set_label(label(meta.get('test', '')) or 'Preparing UI worker')
            state = 'Live' if meta['state'] == 'live' else label(meta.get('detail', 'Waiting for frames'))
            self.state.set_label(f"{label(meta.get('phase', ''), 32)} · {state} · View only")

    class Viewer(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
            self.feeds = feeds if feeds is not None else Feeds()
            self.window = None
            self.views = {}

        def do_activate(self):
            if self.window is not None:
                return
            self.window = Gtk.ApplicationWindow(application=self, title=TITLE)
            set_automation_id(self.window, 'ui-watch-window')
            self.window.set_icon_name(APPLICATION_ID)
            self.window.set_default_size(1200, 850)
            header = Gtk.HeaderBar()
            add_identified_window_controls(header, 'ui-watch-window-controls')
            close = Gtk.Button(icon_name='window-close-symbolic', tooltip_text='Close viewer')
            close.update_property([Gtk.AccessibleProperty.LABEL], ['Close viewer'])
            set_automation_id(close, 'ui-watch-close')
            close.connect('clicked', lambda *_: self.window.close())
            header.pack_end(close)
            self.window.set_titlebar(header)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
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
                                    margin_top=6, margin_bottom=6)
            set_automation_id(self.status, 'ui-watch-status')
            box.append(self.tab_bar)
            box.append(self.tabs)
            box.append(self.status)
            self.window.set_child(box)
            self.window.present()
            self.timer = GLib.timeout_add(100, self.tick)

        def select(self, button, page):
            if button.get_active():
                self.tabs.set_visible_child(page)

        def tick(self):
            frames = self.feeds.poll()
            changed = False
            for run in tuple(self.views):
                if run not in frames:
                    overview, detail, tab, _sequence = self.views.pop(run)
                    if tab.get_active():
                        self.all_tab.set_active(True)
                    self.grid.remove(overview)
                    self.tabs.remove(detail)
                    self.tab_bar.remove(tab)
                    changed = True
            for run, frame in frames.items():
                if run not in self.views:
                    overview = View('ui-watch-grid-' + run)
                    detail = View('ui-watch-branch-' + run)
                    name = label(frame[1].get('branch', ''), 120)
                    tab = Gtk.ToggleButton(label=name or f"Worker {frame[1].get('worker', run[:6])}")
                    set_automation_id(tab, 'ui-watch-tab-' + run)
                    tab.set_group(self.all_tab)
                    self.tabs.add_named(detail, run)
                    tab.connect('toggled', self.select, detail)
                    self.tab_bar.append(tab)
                    self.views[run] = [overview, detail, tab, 0]
                    changed = True
                overview, detail, _tab, sequence = self.views[run]
                if frame[0] != sequence:
                    texture = None
                    if frame[1]['state'] == 'live':
                        meta = frame[1]
                        texture = Gdk.MemoryTexture.new(meta['width'], meta['height'],
                            Gdk.MemoryFormat.B8G8R8X8, GLib.Bytes.new(frame[2]), meta['stride'])
                    overview.update(frame, texture)
                    detail.update(frame, texture)
                    self.views[run][3] = frame[0]
            if changed:
                for index, (overview, *_rest) in enumerate(self.views.values()):
                    if overview.get_parent() is not None:
                        self.grid.remove(overview)
                    self.grid.attach(overview, index % 2, index // 2, 1, 1)
            count = len(self.views)
            self.status.set_label(f'{count} active UI worker(s) · View only' if count else WAITING)
            return True

        def do_shutdown(self):
            if hasattr(self, 'timer'):
                GLib.source_remove(self.timer)
            self.feeds.close()
            Gtk.Application.do_shutdown(self)

    return Viewer()


def run_viewer():
    """Keep native GTK diagnostics out of the launching terminal's live UI."""
    directory = Path(tempfile.mkdtemp(prefix='onpc-ui-viewer-', dir='/var/tmp'))
    log_path = directory / 'viewer.log'
    print(f'UI viewer diagnostics: {log_path}', flush=True)
    # GTK writes directly to fd 2; redirecting Python's sys.stderr is insufficient.
    # Restore the caller's streams even when application construction fails.
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
                        return application().run(['watch-ui'])
                    finally:
                        sys.stdout.flush()
                        sys.stderr.flush()
            finally:
                os.dup2(stderr, 2)
                os.close(stderr)
        finally:
            os.dup2(stdout, 1)
            os.close(stdout)


def main():
    import argparse
    from e2e_watch_viewer import desktop_launch_command
    parser = argparse.ArgumentParser(description='Watch UI tests. Open or close this window at any time.')
    parser.add_argument('--desktop-session', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error('launch as your desktop user')
    try:
        snap = Path('/proc/self/attr/current').read_text().startswith('snap.')
    except FileNotFoundError:
        snap = False
    if snap:
        if args.desktop_session:
            parser.error('desktop session still has editor Snap identity')
        command = desktop_launch_command()
        command[-2] = str(Path(__file__).resolve().with_name('watch-ui'))
        return subprocess.run(command, check=False).returncode
    return run_viewer()
