"""Drive the real spectator window on the test-owned private compositor.

The outer UI test owns functional observations and input through public AT-SPI
IDs. This process only produces synthetic transport states and retains the
rendering checks that cannot be expressed as semantic UI acceptance.
"""

import json
import mmap
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import Frames, SIZE
from e2e_watch_viewer import Feed, application

mode = os.environ.get('ONPC_WATCH_LIVE', '0')
live = mode != '0'
output = Path(os.environ['ONPC_WATCH_EVIDENCE'])
control = Path(os.environ['ONPC_WATCH_CONTROL'])
source = None


class FixtureFeed(Feed):
    invocation_progress = None
    invocation_activity = None

    def activity(self):
        return self.invocation_activity

    def progress(self):
        return self.invocation_progress

    def connect(self):
        if source is None:
            raise FileNotFoundError
        self.memory = mmap.mmap(source.read_fd, SIZE, access=mmap.ACCESS_READ)
        self.sequence = 0
        self.last_frame = time.monotonic()


feed = Feed() if live else FixtureFeed()
app = application(feed)
from gi.repository import GLib, Vte
started = time.monotonic()
stage = 0
resume_started = None
evidence = {'live': live, 'frames': 0, 'reconnects': 0, 'max_age_ms': 0}
failure = None
progress = dict(current=3, total=5, case_id='3', title='Parent child discovery',
                step='For both variants, reject the wrong-account prompt. ' * 40,
                operation='Selecting [Existing child] from the child selector ' * 20)


def publish_evidence():
    output.write_text(json.dumps(evidence))


def advance_requested(value):
    try:
        return control.read_text() == str(value)
    except FileNotFoundError:
        return False


def inspect():
    global source, stage, failure, resume_started
    try:
        if app.window is None:
            return True
        elapsed = time.monotonic() - started
        if live:
            if app.screen.texture is not None:
                evidence['frames'] += 1
                evidence['max_age_ms'] = max(evidence['max_age_ms'],
                    (time.monotonic_ns() - app.screen.meta['updated_ns']) / 1e6)
                if mode == 'cycle' and elapsed > 3 and evidence['frames'] > 20:
                    evidence['closed_during_live_attempt'] = True
                    publish_evidence()
                if elapsed > (stage + 1) * 3 and stage < 6:
                    feed.close()
                    stage += 1
                    evidence['reconnects'] += 1
            elif evidence['frames'] > 20 and not (Path('/run/onpc-e2e-watch') /
                    str(os.getuid()) / 'current.json').exists():
                evidence['stopped_window_still_open'] = True
                publish_evidence()
            assert elapsed < 1200, 'Live attempt did not end within qualification deadline'
            return True

        if stage == 0 and advance_requested(1):
            source = Frames('a' * 32)
            source.publish(b'\0\0\xff\0' * 12, b'\xff' * 4, state='live', width=4, height=3,
                stride=16, format=0x20020888, cursor_width=1, cursor_height=1,
                cursor_x=2, cursor_y=1, cursor_on=True, progress=progress)
            stage = 1
        elif stage == 1 and app.screen.texture is not None:
            # Pixel/cursor format and ellipsis are rendering mechanics, not
            # target selection, readiness, or functional acceptance.
            assert app.screen.texture.get_width() == 4 and app.screen.cursor is not None
            assert app.step.get_layout().get_line_count() <= 3
            assert app.status.get_layout().get_line_count() == 1
            assert app.step.get_layout().is_ellipsized()
            assert app.status.get_layout().is_ellipsized()
            assert app.screen.texture.save_to_png(str(output.with_suffix('.png')))
            evidence['frame_format_and_progress_layout'] = True
            publish_evidence()
            stage = 2
        elif stage == 2 and advance_requested(2):
            source.close()
            source = None
            now = time.monotonic_ns()
            feed.invocation_progress = dict(current=4, total=5, case_id='4',
                title='Next case', step='', operation='Preparing VM: check-system: [stage:isolated]',
                started_ns=now - 3660_000_000_000, case_started_ns=now - 120_000_000_000)
            feed.invocation_activity = dict(run='a' * 32, sequence=1,
                offset=0, text='SSH $ apt-get install\n\x1b[1;32mPASS\x1b[0m\n'
                    '\x1b[1;31mREBOOT REQUIRED\x1b[0m\n')
            stage = 3
        elif stage == 3 and app.screen.texture is None and advance_requested(3):
            # VTE remains a passive renderer with no input or PTY. Color
            # encoding is mechanical; the outer test reads visible output.
            assert not app.terminal.get_input_enabled()
            assert app.terminal.get_pty() is None
            html = app.terminal.get_text_format(Vte.Format.HTML)
            assert '#EF2929' in html.upper() and '#8AE234' in html.upper(), html
            evidence['terminal_is_read_only_and_colored'] = True
            feed.invocation_progress = None
            feed.invocation_activity = None
            source = Frames('b' * 32)
            now = time.monotonic_ns()
            source.publish(b'\xff\0\0\0' * 12, state='live', width=4, height=3,
                           stride=16, format=0x20020888, progress=dict(progress,
                               step='First step after preparation', operation='Opening About',
                               started_ns=now, case_started_ns=now, operation_started_ns=now))
            stage = 4
        elif stage == 4 and app.screen.texture is not None:
            assert app.screen.meta['run'] == 'b' * 32
            assert not app.screen.get_focusable()
            app.window.set_default_size(700, 600)
            resume_started = time.monotonic()
            evidence['resumed_frame_in_same_viewer'] = True
            publish_evidence()
            stage = 5
        elif stage == 5 and time.monotonic() - resume_started >= 1.1:
            assert (source.meta['width'], source.meta['height']) == (4, 3)
            evidence['resize_did_not_change_guest'] = True
            publish_evidence()
            stage = 6
        elif stage == 6 and advance_requested(4):
            source.publish(progress={})
            feed.invocation_activity = dict(run='c' * 32, sequence=1, offset=0,
                text='SSH $ diagnostic\nVM observation ready\n',
                operation_active=True, operation_priority=2,
                operation='Inspecting the VM greeter', operation_started_ns=time.monotonic_ns())
            stage = 7
        elif stage == 7 and advance_requested(5):
            feed.invocation_activity.update(operation='VM observation complete', operation_active=False)
            stage = 8
        if stage < 6:
            assert elapsed < 20, 'Fixture viewer did not complete its transitions'
        return True
    except BaseException as error:
        failure = error
        app.window.close()
        return False


GLib.timeout_add(100, inspect)
try:
    result = app.run(['e2e-watch-test'])
finally:
    if source is not None:
        source.close()
    publish_evidence()
if failure is not None:
    raise failure
raise SystemExit(result)
