"""Exercise pane isolation with a small VT screen, including narrow observers."""

import io
import json
import os
import re
import signal
import select
import termios

import pytest
from rich.cells import get_character_cell_size

from launcher_render import LauncherDisplay
from launcher_progress import publish_progress, read_progress, repair_progress
import regression
import regression_session


class Terminal(io.StringIO):
    def __init__(self, width=80, height=24):
        super().__init__()
        self.normal_screen = None
        self.scrollback = []
        self.cursor_visible = True
        self.resize(width, height)

    def resize(self, width, height):
        if getattr(self, 'size', None) == os.terminal_size((width, height)):
            return
        self.size = os.terminal_size((width, height))
        self.cells = [[' '] * width for _ in range(height)]
        self.row = self.column = 0

    def isatty(self):
        return True

    def write(self, value):
        result = super().write(value)
        for token in re.split(r'(\x1b\[[0-?]*[ -/]*[@-~])', value):
            if token.startswith('\x1b['):
                args, operation = token[2:-1], token[-1:]
                if args == '?1049' and operation == 'h':
                    self.normal_screen = ([row[:] for row in self.cells], self.row, self.column)
                elif args == '?1049' and operation == 'l':
                    self.cells, self.row, self.column = self.normal_screen
                    self.normal_screen = None
                elif args == '?25':
                    self.cursor_visible = operation == 'h'
                elif operation == 'H':
                    row, _, column = args.partition(';')
                    self.row, self.column = int(row or 1) - 1, int(column or 1) - 1
                elif operation == 'J' and args == '2':
                    self.cells = [[' '] * self.size.columns for _ in range(self.size.lines)]
                elif operation == 'K' and args == '2':
                    self.cells[self.row] = [' '] * self.size.columns
                continue
            for char in token:
                if char == '\n':
                    self.row += 1
                    self.column = 0
                    continue
                width = get_character_cell_size(char)
                if self.column + width > self.size.columns:
                    self.row += 1
                    self.column = 0
                if self.row >= self.size.lines:
                    if self.normal_screen is None:
                        self.scrollback.append(''.join(self.cells[0]).rstrip())
                    self.cells.pop(0)
                    self.cells.append([' '] * self.size.columns)
                    self.row = self.size.lines - 1
                if width:
                    self.cells[self.row][self.column] = char
                    self.column += width
        return result

    def visible(self):
        return '\n'.join(''.join(row).rstrip() for row in self.cells)


@pytest.fixture
def terminal(monkeypatch):
    terminal = Terminal()
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setattr('launcher_render.shutil.get_terminal_size', lambda **kwargs: terminal.size)
    return terminal


def test_streaming_output_and_cursor_controls_cannot_cover_controller(terminal):
    display = LauncherDisplay(terminal)
    steps = [{'key': '1', 'lines': ['Task 027: Implement customer behavior',
                                  'Session 1: Writing task code + host validation']}]
    display.update(steps, [])
    for index in range(60):
        display.write(f'\033[2J\033[Hcommand result {index}\n')
        visible = terminal.visible()
        assert visible.startswith('\n'.join(steps[0]['lines']))
        assert f'command result {index}' in visible
    assert 'command result 0\n' not in terminal.visible()
    assert terminal.getvalue().count('\033[?1049h') == 1
    display.close()
    assert terminal.getvalue().count('\033[?1049l') == 1


def test_completion_rule_follows_terminal_width_on_resize(terminal):
    display = LauncherDisplay(terminal)
    display.write('─' * 100 + '\nTask 001 complete.\n')
    assert '─' * 79 in terminal.visible()
    terminal.resize(47, 24)
    display.draw()
    assert '─' * 46 in terminal.visible()
    assert '─' * 47 not in terminal.visible()
    display.close()
    replay = terminal.getvalue().split('\033[?1049l')[-1]
    assert '─' * 46 in replay and '─' * 47 not in replay


def test_latest_two_steps_wrap_and_survive_resize_without_ellipsis(terminal):
    display = LauncherDisplay(terminal)
    steps = [{'key': str(index), 'lines': [f'Task {index}: A long customer task title that must stay visible',
                                         f'Session {index}: Writing task code + host validation']}
             for index in range(1, 5)]
    for width, height in [(80, 24), (35, 20), (110, 30)]:
        terminal.resize(width, height)
        display.update(steps, [])
        display.write('latest detailed output\n')
        visible = terminal.visible()
        assert 'Task 1:' not in visible and 'Task 2:' not in visible
        assert 'Task 3:' in visible and 'Task 4:' in visible
        # Folding is permitted; every word of both major steps must survive.
        normalized = ' '.join(visible.split())
        for step in steps[-2:]:
            for line in step['lines']:
                assert line in normalized
        assert 'latest detailed output' in visible
        assert '…' not in visible


def test_shared_task_heading_appears_once_and_survives_small_terminal(terminal):
    display = LauncherDisplay(terminal)
    heading = '\033[1mTask 005a\033[22m: Start a graphical journey before product installation'
    steps = [
        {'key': str(index), 'lines': [heading, f'Session [{index}/{index}]: Live VM test {index - 1}']}
        for index in (2, 3)
    ]
    display.update(steps[:1], [])
    display.update(steps, [])
    for width, height in [(80, 24), (35, 20), (110, 30)]:
        terminal.resize(width, height)
        display.draw()
        visible = ' '.join(terminal.visible().split())
        assert visible.count('Task 005a:') == 1
        assert 'Start a graphical journey before product installation' in visible
        assert 'Session [2/2]: Live VM test 1' in visible
        assert 'Session [3/3]: Live VM test 2' in visible
    terminal.resize(80, 5)
    display.draw()
    visible = terminal.visible()
    assert visible.startswith('Task 005a:')
    assert 'Session [2/2]' not in visible
    assert 'Session [3/3]: Live VM test 2' in visible
    assert list(display.step_history.values()) == [step['lines'] for step in steps]


def test_test_tree_updates_stay_below_controller_and_quiet_frames_do_not_repaint(terminal):
    display = LauncherDisplay(terminal)
    steps = [{'key': 'unit', 'lines': ['Category: unit (1/2) | Overall - 10% (1/10)']}]
    details = [f'[Pending] Suite {index}' for index in range(40)]
    details.append('[Running] Current test - 10%')
    display.update(steps, details)
    assert terminal.visible().startswith(steps[0]['lines'][0])
    assert '[Running] Current test - 10%' in terminal.visible()
    before = terminal.getvalue()
    display.update(steps, details)
    assert terminal.getvalue() == before
    details[-1] = '[Running] Current test - 20%'
    display.update(steps, details)
    assert terminal.visible().startswith(steps[0]['lines'][0])
    assert '[Running] Current test - 20%' in terminal.visible()
    assert 'Category:' not in terminal.getvalue()[len(before):]


def test_wide_characters_in_child_rows_cannot_scroll_header_off_screen(terminal):
    terminal.resize(32, 8)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'live', 'lines': ['Task 024: Live verification']}],
                   ['[Running] ' + '界' * 40] * 30)
    assert terminal.visible().startswith('Task 024: Live verification\n')


def test_mouse_scroll_follows_clicked_pane_and_defaults_to_bottom(terminal):
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    for index in range(10):
        display.update([{'key': str(index), 'lines': [f'Step {index}']}], [])
    display.write(''.join(f'output {index}\n' for index in range(30)))
    initial = terminal.visible().splitlines()
    # Pointer location alone does not change the default bottom focus.
    display.handle_input(b'\x1b[<64;2;1M')
    bottom_scrolled = terminal.visible().splitlines()
    assert bottom_scrolled[0] == initial[0]
    assert bottom_scrolled[2:] != initial[2:]
    assert 'output 26' in terminal.visible() and 'output 29' not in terminal.visible()
    # Click top, then scroll with the pointer over bottom.
    display.handle_input(b'\x1b[<0;2;1M\x1b[<0;2;1m\x1b[<64;2;8M')
    top_scrolled = terminal.visible().splitlines()
    assert top_scrolled[0] == 'Step 6'
    assert top_scrolled[2:] == bottom_scrolled[2:]
    display.handle_input(b'\x1b[<0;2;8M\x1b[<65;2;1M')
    assert terminal.visible().splitlines()[0] == 'Step 6'
    assert terminal.visible().splitlines()[2:] == initial[2:]


def test_bottom_scrollbar_shows_position_and_accepts_track_clicks(terminal):
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'task', 'lines': ['Task']}], [])
    display.write(''.join(f'output {index}\n' for index in range(30)))
    assert terminal.cells[-1][-1] == '█'
    assert terminal.cells[2][-1] == '░'

    display.handle_input(b'\x1b[<0;50;3M')
    assert 'output 0' in terminal.visible()
    assert terminal.cells[2][-1] == '█'
    assert terminal.cells[-1][-1] == '░'

    display.handle_input(b'\x1b[<0;50;10M')
    assert 'output 29' in terminal.visible()
    assert terminal.cells[-1][-1] == '█'


@pytest.mark.parametrize('width', [12, 50])
def test_bottom_scrollbar_stays_at_right_edge_for_different_line_lengths(terminal, width):
    terminal.resize(width, 10)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'task', 'lines': ['Task']}], [])
    display.write(('short\n\n界界\n' + 'wrapped output ' * 8 + '\n') * 5)
    for row in terminal.cells[2:]:
        assert row[-1] in ('░', '█')
        assert not {'░', '█'}.intersection(row[:-1])


def test_scrollbar_thumb_drags_without_jumping_and_stops_on_release(terminal):
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'task', 'lines': ['Task']}], [])
    display.write(''.join(f'output {index}\n' for index in range(30)))
    initial = terminal.visible()
    # Grab the lower cell of the two-cell thumb without moving the viewport.
    display.handle_input(b'\x1b[<0;50;10M')
    assert terminal.visible() == initial
    # Motion remains captured when the pointer leaves the scrollbar column.
    for byte in b'\x1b[<32;25;1M':
        display.handle_input(bytes([byte]))
    assert ''.join(terminal.cells[2][:-1]).rstrip() == 'output 0'
    display.handle_input(b'\x1b[<32;25;6M')
    assert 0 < display.offsets['bottom'] < 22
    display.handle_input(b'\x1b[<0;25;6m')
    released = terminal.visible()
    display.handle_input(b'\x1b[<32;50;10M')
    assert terminal.visible() == released

    thumb_row = next(index + 1 for index, row in enumerate(terminal.cells) if row[-1] == '█')
    display.handle_input(f'\x1b[<0;50;{thumb_row}M'.encode())
    display.handle_input(b'\x1b[<32;50;15M\x1b[<0;50;15m')
    assert display.offsets['bottom'] == 0
    display.write('output 30\n')
    assert 'output 30' in terminal.visible()


def test_scrolled_transcript_stays_put_while_output_arrives(terminal):
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'task', 'lines': ['Task']}], [])
    display.write(''.join(f'output {index}\n' for index in range(30)))
    display.handle_input(b'\x1b[<64;2;8M')
    visible = [''.join(row[:-1]) for row in terminal.cells]
    display.write('output 30')
    assert [''.join(row[:-1]) for row in terminal.cells] == visible
    display.write('\n')
    assert [''.join(row[:-1]) for row in terminal.cells] == visible


def test_scrollback_evicts_old_output_and_clamps_scrolled_view(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_LINES', 20)
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    display.write(''.join(f'output {index}\n' for index in range(20)))
    display.offsets['bottom'] = 1000
    display.draw()
    display.write(''.join(f'output {index}\n' for index in range(20, 50)))
    assert list(display.transcript) == [f'output {index}' for index in range(30, 50)]
    assert 'output 30' in terminal.visible()
    assert display.offsets['bottom'] == 11
    display.offsets['bottom'] = 0
    display.draw()
    assert 'output 49' in terminal.visible()


def test_partial_and_unsaved_output_have_a_text_budget(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_CHARACTERS', 128)
    display = LauncherDisplay(terminal)
    for _ in range(30):
        display.write('old text ' * 4, saved=False)
        assert len(display.pending) + sum(map(len, display.transcript)) <= 128
        assert sum(map(len, display.unsaved)) <= 128
    display.write('newest text', final=True, saved=False)
    assert not display.pending
    assert ''.join(display.transcript).endswith('newest text')
    assert ''.join(display.unsaved).endswith('newest text')
    assert sum(map(len, display.transcript)) <= 128


def test_wrapped_history_is_bounded_after_resize(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_LINES', 20)
    display = LauncherDisplay(terminal)
    display.write(('long output ' * 12 + '\n') * 20 + 'newest\n')
    terminal.resize(12, 10)
    display.draw()
    rows = display.row_cache['bottom'][1]
    assert len(rows) == 20
    assert rows[-1].plain == 'newest'
    assert 'newest' in terminal.visible()


def test_step_history_has_a_text_budget(terminal, monkeypatch):
    monkeypatch.setattr('launcher_render.SCROLLBACK_CHARACTERS', 128)
    display = LauncherDisplay(terminal)
    for index in range(30):
        display.update([{'key': str(index), 'lines': ['step ' + str(index)] * 10}], [])
        assert sum(len(line) for lines in display.step_history.values() for line in lines) <= 128
    assert list(display.step_history)[-1] == '29'


@pytest.mark.parametrize('reason', ['success', 'error', 'interrupt'])
def test_mouse_input_is_not_echoed_and_terminal_modes_are_restored(terminal, monkeypatch, reason):
    master, slave = os.openpty()
    try:
        original = termios.tcgetattr(slave)
        with os.fdopen(os.dup(slave), 'r') as source:
            monkeypatch.setattr('launcher_render.sys.stdin', source)
            monkeypatch.setattr(terminal, 'fileno', lambda: slave)
            monkeypatch.setattr('launcher_render.os.get_terminal_size', lambda fd: terminal.size)
            monkeypatch.setattr('launcher_render.os.tcgetpgrp', lambda fd: os.getpgrp())
            try:
                with LauncherDisplay(terminal) as display:
                    display.update([{'key': 'task', 'lines': ['Task']}], [])
                    current = termios.tcgetattr(slave)
                    assert not current[3] & (termios.ECHO | termios.ICANON)
                    assert current[3] & termios.ISIG == original[3] & termios.ISIG
                    before = terminal.getvalue()
                    # Empty top pane scroll and terminal arrow fallback must neither
                    # repaint content nor echo raw escape sequences into the screen.
                    os.write(master, b'\x1b[<0;2;1M\x1b[<64;2;1M\x1b[A\x1b[B\x1b[B\x1b')
                    assert select.select([slave], [], [], 1)[0]
                    display.poll_input()
                    assert display.focus == 'top'
                    assert display.offsets == {'top': 0, 'bottom': 0}
                    assert terminal.getvalue() == before
                    assert not select.select([master], [], [], 0)[0]
                    if reason == 'error':
                        raise RuntimeError('test exit')
                    if reason == 'interrupt':
                        raise KeyboardInterrupt
            except (RuntimeError, KeyboardInterrupt):
                if reason == 'success':
                    raise
            assert termios.tcgetattr(slave) == original
            assert '\x1b[?1002h\x1b[?1006h' in terminal.getvalue()
            assert '\x1b[?1002l\x1b[?1006l' in terminal.getvalue()
    finally:
        os.close(master)
        os.close(slave)


def test_mouse_reports_can_arrive_in_fragments_and_scroll_is_bounded(terminal):
    terminal.resize(50, 10)
    display = LauncherDisplay(terminal)
    display.update([{'key': 'task', 'lines': ['Task']}], [])
    display.write(''.join(f'output {index}\n' for index in range(30)))
    for byte in b'\x1b[<64;2;8M':
        display.handle_input(bytes([byte]))
    assert 'output 26' in terminal.visible() and 'output 29' not in terminal.visible()
    display.handle_input(b'\x1b[<64;2;8M' * 100)
    assert ''.join(terminal.cells[2][:-1]).rstrip() == 'output 0'
    display.handle_input(b'\x1b[<65;2;8M' * 100)
    assert 'output 29' in terminal.visible()


def test_progress_reconnects_with_two_steps_and_coalesces_minor_updates(tmp_path):
    for key in ['first', 'second', 'third']:
        publish_progress(tmp_path, key, [key])
    publish_progress(tmp_path, 'third', ['updated'])
    assert read_progress(tmp_path) == [{'key': 'second', 'lines': ['second']},
                                       {'key': 'third', 'lines': ['updated']}]


def test_nested_test_progress_preserves_round_and_never_replaces_repair_status(tmp_path):
    publish_progress(tmp_path, 'test', ['Round 2: Category: unit (1/4)', 'Status: Running tests'])
    (tmp_path / 'test-controller.json').write_text(json.dumps([
        {'key': 'done', 'lines': ['Category: unit (1/1) | Overall - 100% (9/1/10) | Failed']}]))
    steps = repair_progress(tmp_path, read_progress(tmp_path))
    assert steps[-1]['lines'] == ['Round 2: Category: unit (1/4) | Overall - 100% (9/1/10) | Failed',
                                  'Status: Running tests']
    publish_progress(tmp_path, 'repair', [steps[-1]['lines'][0], 'Status: fixing errors'])
    assert repair_progress(tmp_path, read_progress(tmp_path))[-1]['lines'][-1] == 'Status: fixing errors'


def test_controller_counts_refresh_infrequently_and_follow_category_boundaries(tmp_path):
    output = regression_session.SessionOutput(tmp_path, io.StringIO())
    category = regression.Category('Unit bucket', 100, 1, 'Running')
    dashboard = regression.Dashboard([category], output)
    dashboard.controller_category = ('unit', 1, 2)
    dashboard.controller(10, dashboard.render(10))
    initial = read_progress(tmp_path)
    category.done = 20
    dashboard.controller(11, dashboard.render(11))
    assert read_progress(tmp_path) == initial
    dashboard.controller(16, dashboard.render(16))
    assert 'Overall - 20%' in read_progress(tmp_path)[-1]['lines'][0]
    assert len(read_progress(tmp_path)) == 1
    dashboard.controller_category = ('ui', 2, 2)
    dashboard.controller(17, dashboard.render(17))
    assert read_progress(tmp_path)[-1]['lines'][0].startswith('Category: ui (2/2)')
    category.state, category.done = 'Passed', 100
    dashboard.finish()
    assert len(read_progress(tmp_path)) == 2
    assert 'Category: unit (1/2)' in read_progress(tmp_path)[0]['lines'][0]
    assert read_progress(tmp_path)[-1]['lines'][0].endswith('| Passed')


def test_plain_output_accumulates_without_cursor_escapes():
    output = io.StringIO()
    display = LauncherDisplay(output)
    for index in range(4):
        display.update([{'key': str(index), 'lines': [f'Session {index}']}], [])
        display.write(f'output {index}\n')
    display.close()
    assert output.getvalue() == ''.join(f'Session {i}\noutput {i}\n' for i in range(4))


@pytest.mark.parametrize('height', [1, 3, 24])
@pytest.mark.parametrize('reason', ['success', 'interrupt', 'error', 'hup', 'term', 'quit'])
@pytest.mark.parametrize('observer', ['workflow', 'tests'])
def test_observer_preserves_output_on_every_exit(terminal, monkeypatch, tmp_path, height, reason, observer):
    import detached_launcher

    terminal.resize(80, height)
    terminal.write('original shell prompt> ')
    (tmp_path / 'output').write_text('earliest output\n' + 'old output\n' * 2100
                                    + 'agent transcript\nunfinished output')
    signals = {'hup': signal.SIGHUP, 'term': signal.SIGTERM, 'quit': signal.SIGQUIT}
    handlers = {sig: signal.SIG_DFL for sig in signals.values()}
    monkeypatch.setattr(signal, 'getsignal', lambda sig: handlers[sig])
    monkeypatch.setattr(signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
    monkeypatch.delenv(regression_session.FRAME_DIRECTORY, raising=False)

    def output(run, stream, display, **kwargs):
        display.update([{'key': 'task', 'lines': ['controller header', 'session status']}],
                       ['[Running] test details'])
        display.write('agent transcript\nunfinished output')
        if reason == 'interrupt':
            raise KeyboardInterrupt
        if reason == 'error':
            raise RuntimeError('observer failed')
        if reason in signals:
            sig = signals[reason]
            handlers[sig](sig, None)
        return 0

    monkeypatch.setattr(detached_launcher, 'follow_output', output)
    follow = detached_launcher.follow if observer == 'workflow' else regression_session.follow
    if reason == 'success':
        assert follow(tmp_path, terminal) == 0
    else:
        exception = KeyboardInterrupt if reason == 'interrupt' else RuntimeError if reason == 'error' else SystemExit
        with pytest.raises(exception) as caught:
            follow(tmp_path, terminal)
        if reason in signals:
            assert caught.value.code == 128 + signals[reason]
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert 'earliest output\n' in restored
    assert restored.count('old output\n') == 2100
    assert 'controller header' in restored and 'session status' in restored
    assert restored.endswith('agent transcript\nunfinished output\n')
    assert '\033[2J' not in restored and '\033[H' not in restored
    assert '[Running] test details' not in restored
    assert '─' not in restored
    assert '\033[?1049h' not in restored
    assert terminal.normal_screen is None
    assert terminal.cursor_visible
    assert 'original shell prompt> ' in terminal.getvalue().split('\033[?1049h', 1)[0]
    assert 'original shell prompt>' in terminal.scrollback
    assert all(handler == signal.SIG_DFL for handler in handlers.values())


def test_exit_replay_filters_cursor_controls_preserves_color_and_runs_once(terminal, tmp_path):
    log = tmp_path / 'output'
    log.write_text('\033[2J\033[Hfirst output\n\033[31mfinal warning\033[0m\n')
    display = LauncherDisplay(terminal, log_path=log)
    display.write('final warning\n')
    display.close()
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert 'first output' in restored and 'final warning' in restored
    assert '\033[2J' not in restored and '\033[H' not in restored
    assert '\033[31m' in restored
    before = terminal.getvalue()
    display.close()
    assert terminal.getvalue() == before


def test_exit_without_readable_log_preserves_live_transcript(terminal, tmp_path):
    with LauncherDisplay(terminal, log_path=tmp_path / 'missing') as display:
        display.write('observed output\npartial line')
    assert terminal.getvalue().split('\033[?1049l', 1)[1].endswith(
        'observed output\npartial line\n')


@pytest.mark.parametrize('observer', ['workflow', 'tests'])
@pytest.mark.parametrize('finished', [True, False])
def test_real_output_follow_replays_log_and_missing_result_notice(terminal, tmp_path, monkeypatch,
                                                                 observer, finished):
    import detached_launcher

    run = tmp_path / 'run'
    run.mkdir()
    (run / 'output').write_text('first result\nlast result\n')
    publish_progress(run, 'task', ['Task complete' if finished else 'Task running'])
    if finished:
        (run / 'result').write_text('0')
        (run / 'result.json').write_text('{"status": 0}')
    monkeypatch.delenv(regression_session.FRAME_DIRECTORY, raising=False)
    follow = detached_launcher.follow if observer == 'workflow' else regression_session.follow
    assert follow(run, terminal) == (0 if finished else 1)
    restored = terminal.getvalue().split('\033[?1049l', 1)[1]
    assert restored.count('first result\nlast result\n') == 1
    if not finished:
        assert ('run is incomplete' if observer == 'tests' else 'worker ended without a result') in restored


def test_pipe_does_not_replay_saved_log(tmp_path):
    log = tmp_path / 'output'
    log.write_text('old output\nnew output\n')
    stream = io.StringIO()
    with LauncherDisplay(stream, log_path=log) as display:
        display.write('new output\n')
    assert stream.getvalue() == 'new output\n'


def test_display_preserves_custom_and_ignored_signal_handlers(terminal, monkeypatch):
    handlers = {signal.SIGHUP: signal.SIG_IGN, signal.SIGTERM: lambda *_: None,
                signal.SIGQUIT: signal.SIG_DFL}
    original = handlers.copy()
    monkeypatch.setattr(signal, 'getsignal', lambda sig: handlers[sig])
    monkeypatch.setattr(signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
    with LauncherDisplay(terminal):
        assert handlers[signal.SIGHUP] == signal.SIG_IGN
        assert handlers[signal.SIGTERM] is original[signal.SIGTERM]
    assert handlers == original
