"""Combined watcher with private real transports and launcher output files."""

from contextlib import ExitStack
import fcntl
import json
import mmap
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import Frames, SIZE
from e2e_watch_viewer import Feed
from ui_watch_transport import Feeds, Publication
from watch_output import Output
from watch_viewer import application
from test_storage import directory, runtime_directory

root = Path(os.environ['ONPC_WATCH_FIXTURE'])
control, evidence = root / 'control', root / 'evidence.json'
stack = ExitStack()
runtime = stack.enter_context(runtime_directory(prefix='onpc-watch-test-'))
ui_source = None
vm_source = None
locks = {}
stage = ''
result = {}
failure = None


class VM(Feed):
    def connect(self):
        if vm_source is None:
            raise FileNotFoundError
        self.memory = mmap.mmap(vm_source.read_fd, SIZE, access=mmap.ACCESS_READ)
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


app = application(feeds=Feeds(runtime), feed=VM(), output=Output(root))
from gi.repository import GLib, Gtk, Vte


def tick():
    global stage, ui_source, vm_source, failure
    try:
        if app.window is None:
            return True
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
                runner('sessions-host', '\x1b[32mRUN OUTPUT\x1b[0m\n' + 'wrapped text ' * 120 + '\nEND WRAPPED\n')
            elif stage == 'both':
                vm_source = Frames('b' * 32)
                vm_source.publish(b'\x10\x20\x30\0' * 12, state='live', width=4, height=3,
                    stride=16, format=0x20020888, progress=dict(current=1, total=1, case_id='1',
                        title='VM test', step='VM first', operation='VM operation'))
            elif stage == 'split-check':
                result['rows_ratio'] = app.split.get_position() / app.split.get_height()
                # Native split position and terminal reflow are rendering checks,
                # never coordinates for resolving or operating a test target.
                app.pane.set_position(300)
                app.split.set_position(220)
            elif stage == 'hide-vm':
                assert app.selected == 'ui'
                vm_source.publish(progress=dict(vm_source.meta['progress'], step='VM next'))
                result['hidden_vm_sequence'] = app.vm.screen.meta['updated_ns']
                result['hidden_vm_step'] = app.vm.step.get_label()
                result['started'] = time.monotonic()
                runner('fix-tests', '\x1b[31mFIX OUTPUT\x1b[0m\n')
            elif stage == 'hide-ui':
                assert app.selected == 'vm'
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
        if stage == 'hide-vm' and time.monotonic() - result['started'] > .8:
            result['vm_frozen'] = (app.vm.step.get_label() == result['hidden_vm_step']
                and app.vm.screen.meta['updated_ns'] == result['hidden_vm_sequence'])
        if stage == 'hide-ui' and time.monotonic() - result['started'] > .8:
            result['ui_frozen'] = (app.ui.views[ui_source.run][0].description.get_label()
                                   == result['hidden_ui_test'])
        if stage == 'split-check':
            result['dividers_resized'] = (app.pane.get_position() == 300
                                         and app.split.get_position() == 220)
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
    if ui_source is not None:
        ui_source.close()
    if vm_source is not None:
        vm_source.close()
    stack.close()
if failure is not None:
    raise failure
raise SystemExit(status)
