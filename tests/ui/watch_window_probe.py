"""Combined watcher with private real transports and launcher output files."""

from contextlib import ExitStack
import fcntl
import json
import mmap
import os
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import Frames, SIZE
from e2e_watch_viewer import AsyncFeed, Feed
from ui_watch_transport import Feeds, Publication
from watch_output import Output
from watch_viewer import application
from test_storage import directory, runtime_directory

root = Path(os.environ['ONPC_WATCH_FIXTURE'])
if os.environ.get('ONPC_WATCH_CHECKOUTS') == '1':
    from watch_checkout_fixture import run
    raise SystemExit(run(root))
control, evidence = root / 'control', root / 'evidence.json'
stack = ExitStack()
runtime = stack.enter_context(runtime_directory(prefix='onpc-watch-test-'))
ui_source = None
vm_source = None
extra_sources = {}
locks = {}
stage = ''
result = {}
failure = None
stall_vm = threading.Event()
release_vm = threading.Event()
stalled_vm_entered = threading.Event()


class VM(Feed):
    def poll(self, *, pixels=True):
        if self.vm_name == vm_names[-1] and stall_vm.is_set():
            stalled_vm_entered.set()
            release_vm.wait(15)
        return super().poll(pixels=pixels)

    def connect(self):
        source = vm_source if self.vm_name == vm_names[0] else extra_sources.get(self.vm_name)
        if source is None:
            raise FileNotFoundError
        self.memory = mmap.mmap(source.read_fd, SIZE, access=mmap.ACCESS_READ)
        self.sequence = 0
        self.last_frame = time.monotonic()

    def activity(self):
        return None

    def progress(self):
        return None


def runner(kind, text):
    base = directory(kind, root=root)
    run = base / ('a' * 32)
    run.mkdir(mode=0o700)
    (base / 'current.json').write_text(json.dumps({'run': run.name}))
    (run / 'output').write_text(text)
    (run / 'frame.json').write_text(json.dumps(['RUN PROGRESS']))
    owner = base / 'owner' if kind == 'fix-tests' else run / 'owner'
    lock = stack.enter_context(owner.open('wb'))
    owner.chmod(0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)
    locks[kind] = lock


vm_names = [os.environ['ONPC_TEST_VM'], 'Fixture-VM-2', 'Fixture-VM-3',
            'Fixture-VM-4', 'Fixture-VM-5']
vm_feeds = {name: AsyncFeed(VM(name)) for name in vm_names}
app = application(feeds=Feeds(runtime), vm_feeds=vm_feeds,
                  output=Output(root))
import gi
gi.require_version('Vte', '3.91')
from gi.repository import GLib, Gtk, Vte


def tick():
    global stage, ui_source, vm_source, failure
    try:
        if app.window is None:
            return True
        app.vm = app.vms[app.vm_keys[vm_names[0]]]
        requested = control.read_text() if control.exists() else ''
        if requested != stage:
            stage = requested
            if stage == 'ui':
                result['columns_ratio'] = app.pane.get_position() / app.pane.get_width()
                result['icon'] = app.window.get_icon_name()
                ui_source = Publication(runtime)
                ui_source.frames.publish(b'\x10\x20\x30\0' * 12, state='live', worker=1,
                    width=4, height=3, stride=16, format=0x20020888, test='UI first', phase='call')
                result['run'] = ui_source.run
                # Keep the observed header and tail in the viewport at the
                # narrower default split, while forcing the long line to wrap.
                columns, rows = app.terminal.get_column_count(), app.terminal.get_row_count()
                repetitions = max(4, min(120, columns * max(1, rows - 8) // len('wrapped text ')))
                result['wrap_repetitions'] = repetitions
                runner('sessions-host', '\x1b[32mRUN OUTPUT\x1b[0m\n' +
                       'wrapped text ' * repetitions + '\nEND WRAPPED\n')
            elif stage == 'both':
                vm_source = Frames('b' * 32)
                vm_source.publish(b'\x10\x20\x30\0' * 12, state='live', width=4, height=3,
                    stride=16, format=0x20020888, progress=dict(current=1, total=1, case_id='1',
                        title='VM test', step='VM first', operation='VM operation'))
            elif stage == 'split-check':
                # Native split position and terminal reflow are rendering checks,
                # never coordinates for resolving or operating a test target.
                app.pane.set_position(300)
            elif stage == 'hide-vm':
                assert app.selected == 'ui-' + ui_source.run
                vm_source.publish(progress=dict(vm_source.meta['progress'], step='VM next'))
                result['hidden_vm_sequence'] = app.vm.screen.meta['updated_ns']
                result['hidden_vm_step'] = app.vm.step.get_label()
                result['started'] = time.monotonic()
                runner('fix-tests', '\x1b[31mFIX OUTPUT\x1b[0m\n')
            elif stage == 'hide-ui':
                assert app.selected == app.vm_keys[vm_names[0]]
                result['hidden_ui_test'] = app.ui.views[ui_source.run][0].description.get_label()
                ui_source.frames.publish(test='UI next')
                result['started'] = time.monotonic()
            elif stage == 'vm-only':
                ui_source.close()
                ui_source = None
                fcntl.flock(locks['fix-tests'], fcntl.LOCK_UN)
            elif stage == 'idle':
                vm_source.close()
                vm_source = None
                fcntl.flock(locks['sessions-host'], fcntl.LOCK_UN)
            elif stage == 'unlocked':
                vm_source.publish(lease_locked=False)
            elif stage == 'stall-vm':
                release_vm.clear()
                stall_vm.set()
                vm_source.publish(progress=dict(vm_source.meta['progress'], step='Healthy during stall'))
                path = directory('sessions-host', root=root) / ('a' * 32) / 'output'
                with path.open('a') as log:
                    log.write('RUN WHILE VM STALLED\n')
            elif stage == 'release-vm':
                stall_vm.clear()
                release_vm.set()
            elif stage.startswith('vms-'):
                count = int(stage.removeprefix('vms-'))
                for index, name in enumerate(vm_names[1:], 1):
                    if index < count and name not in extra_sources:
                        source = Frames(str(index) * 32)
                        source.publish(b'\x10\x20\x30\0' * 12, state='live', width=4, height=3,
                                       stride=16, format=0x20020888)
                        extra_sources[name] = source
                    elif index >= count and name in extra_sources:
                        extra_sources.pop(name).close()
            elif stage == 'double-click':
                view = app.cells[str(app.primary.root), app.vm_keys[vm_names[2]]][0]
                controllers = view.observe_controllers()
                for index in range(controllers.get_n_items()):
                    controller = controllers.get_item(index)
                    if isinstance(controller, Gtk.GestureClick):
                        controller.emit('pressed', 2, 0., 0.)
        if stage == 'hide-vm' and time.monotonic() - result['started'] > .8:
            result['vm_frozen'] = (app.vm.step.get_label() == result['hidden_vm_step']
                and app.vm.screen.meta['updated_ns'] == result['hidden_vm_sequence'])
        if stage == 'hide-ui' and time.monotonic() - result['started'] > .8:
            result['ui_frozen'] = (app.ui.views[ui_source.run][0].description.get_label()
                                   == result['hidden_ui_test'])
        if stage == 'split-check':
            result['dividers_resized'] = app.pane.get_position() == 300
            result['terminal_columns'] = app.terminal.get_column_count()
            result['no_horizontal_scroll'] = app.output_scroll.get_policy()[0] == Gtk.PolicyType.NEVER
            result['terminal_readonly'] = (not app.terminal.get_input_enabled()
                                           and app.terminal.get_pty() is None)
            result['terminal_colored'] = '#008000' in app.terminal.get_text_format(Vte.Format.HTML).upper()
            app.terminal.select_all()
            result['terminal_selectable'] = app.terminal.get_has_selection()
            app.copy_selection()
            app.terminal.unselect_all()
        if ui_source is not None:
            ui_source.serve()
            ui_source.frames.publish()
        if vm_source is not None:
            vm_source.publish()
        for source in extra_sources.values():
            source.publish()
        result['vm_names'] = vm_names
        result['vm_cells'] = {
            name: list(app.vm_grid.query_child(app.cells[str(app.primary.root), key][0]))
            for name, key in app.vm_keys.items()
            if app.cells[str(app.primary.root), key][0].get_parent() == app.vm_grid}
        result['viewer_cells'] = {
            key: list(app.vm_grid.query_child(cell))
            for (name, key), (cell, _title) in app.cells.items()
            if cell.get_parent() == app.vm_grid}
        result['vm_tabs'] = {name: app.buttons[key].get_opacity()
                             for name, key in app.vm_keys.items()}
        result['selected'] = app.selected
        result['stage'] = stage
        result['output_active'] = app.output_active
        result['output_status'] = app.output_status.get_label()
        result['stalled_vm_entered'] = stalled_vm_entered.is_set()
        result['terminal_text'] = app.terminal.get_text_format(Vte.Format.TEXT)
        result['terminal_size'] = [app.terminal.get_column_count(), app.terminal.get_row_count()]
        result['terminal_dimensions'] = [app.terminal.get_width(), app.terminal.get_height()]
        evidence.write_text(json.dumps(result))
        return True
    except BaseException as error:
        failure = error
        app.window.close()
        return False


GLib.timeout_add(50, tick)
try:
    status = app.run(['watch-test'])
finally:
    release_vm.set()
    if ui_source is not None:
        ui_source.close()
    if vm_source is not None:
        vm_source.close()
    for source in extra_sources.values():
        source.close()
    for feed in vm_feeds.values():
        feed.close()
        feed.thread.join(2)
        assert not feed.thread.is_alive()
    stack.close()
if failure is not None:
    raise failure
raise SystemExit(status)
