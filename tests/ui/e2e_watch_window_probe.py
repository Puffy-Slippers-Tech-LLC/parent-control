"""Exercise the real spectator window on the test-owned private compositor."""

import json
import mmap
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from e2e_watch_protocol import Frames, SIZE
from e2e_watch_viewer import Feed, application, TITLE

mode = os.environ.get('ONPC_WATCH_LIVE', '0')
live = mode != '0'
output = Path(os.environ['ONPC_WATCH_EVIDENCE'])
source = None


class FixtureFeed(Feed):
    def connect(self):
        if source is None:
            raise FileNotFoundError
        self.memory = mmap.mmap(source.read_fd, SIZE, access=mmap.ACCESS_READ)
        self.sequence = 0
        self.last_frame = time.monotonic()


feed = Feed() if live else FixtureFeed()
app = application(feed)
from gi.repository import GLib
started = time.monotonic()
stage = 0
evidence = {'live': live, 'frames': 0, 'reconnects': 0, 'max_age_ms': 0}
failure = None
progress = dict(current=3, total=5, case_id='3', title='Parent child discovery',
                step='For both variants, reject the wrong-account prompt. ' * 40,
                operation='Selecting [Existing child] from the child selector ' * 20)


def inspect():
    global source, stage, failure
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
                    return finish()
                if elapsed > (stage + 1) * 3 and stage < 6:
                    feed.close()
                    stage += 1
                    evidence['reconnects'] += 1
            elif evidence['frames'] > 20 and not (Path('/run/onpc-e2e-watch') /
                    str(os.getuid()) / 'current.json').exists():
                assert app.window.get_mapped()
                evidence['stopped_window_still_open'] = True
                return finish()
            assert elapsed < 1200, 'Live attempt did not end within qualification deadline'
            return True
        if stage == 0 and elapsed > .3:
            assert app.window.get_mapped() and app.screen.texture is None
            evidence['waiting_window_open'] = True
            source = Frames('a' * 32)
            source.publish(b'\0\0\xff\0' * 12, b'\xff' * 4, state='live', width=4, height=3,
                stride=16, format=0x20020888, cursor_width=1, cursor_height=1,
                cursor_x=2, cursor_y=1, cursor_on=True, progress=progress)
            stage = 1
        elif stage == 1 and app.screen.texture is not None:
            assert app.screen.texture.get_width() == 4 and app.screen.cursor is not None
            assert app.window.get_title() == '[3/5] [3]: Parent child discovery'
            assert app.step.get_text() == progress['step']
            assert app.status.get_text() == progress['operation']
            assert app.step.get_layout().get_line_count() <= 3
            assert app.status.get_layout().get_line_count() == 1
            assert app.step.get_layout().is_ellipsized()
            assert app.status.get_layout().is_ellipsized()
            evidence['progress_visible_and_truncated'] = True
            assert app.screen.texture.save_to_png(str(output.with_suffix('.png')))
            source.close()
            source = None
            stage = 2
        elif stage == 2 and app.screen.texture is None:
            assert app.window.get_mapped()
            assert app.window.get_title() == TITLE and app.step.get_text() == ''
            evidence['stopped_window_still_open'] = True
            source = Frames('b' * 32)
            source.publish(b'\xff\0\0\0' * 12, state='live', width=4, height=3,
                           stride=16, format=0x20020888)
            stage = 3
        elif stage == 3 and app.screen.texture is not None:
            assert app.screen.meta['run'] == 'b' * 32 and app.window.get_mapped()
            assert app.window.get_title() == TITLE and app.step.get_text() == ''
            assert not app.screen.get_focusable()
            app.window.set_default_size(700, 600)
            evidence['resumed_same_window'] = True
            stage = 4
        elif stage == 4:
            assert (source.meta['width'], source.meta['height']) == (4, 3)
            evidence['resize_did_not_change_guest'] = True
            return finish()
        assert elapsed < 15, 'Fixture viewer did not complete its transitions'
        return True
    except BaseException as error:
        failure = error
        app.window.close()
        return False


def finish():
    output.write_text(json.dumps(evidence))
    app.window.close()  # Explicit test-owner action; no runner owns user windows.
    return False


GLib.timeout_add(100, inspect)
try:
    result = app.run(['e2e-watch-test'])
finally:
    if source is not None:
        source.close()
if failure is not None:
    raise failure
raise SystemExit(result)
