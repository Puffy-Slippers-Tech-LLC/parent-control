"""Exercise pane isolation with a small VT screen, including narrow observers."""

import io
import json
import os
import re

import pytest
from rich.cells import get_character_cell_size

from launcher_render import LauncherDisplay
from launcher_progress import publish_progress, read_progress, repair_progress
import regression
import regression_session


class Terminal(io.StringIO):
    def __init__(self, width=80, height=24):
        super().__init__()
        self.resize(width, height)

    def resize(self, width, height):
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
                if operation == 'H':
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
    monkeypatch.setattr('launcher_render.shutil.get_terminal_size', lambda: terminal.size)
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
